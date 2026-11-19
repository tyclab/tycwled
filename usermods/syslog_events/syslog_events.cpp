/*
 * syslog_events — WLED's notable events as RFC3164 syslog over UDP, without a debug build.
 *
 * Boot (reset reason, the previous run's last breadcrumbs, the crash record if the panic
 * hook is built in), Wi-Fi connect/loss with RSSI, heap-low crossings, OTA start/failure,
 * WLED errorFlag codes, live-override changes, and an hourly status line so a log-quiet
 * alert can tell a dead lamp from a quiet one.
 *
 * LED timing: loop() does O(1) work per pass, samples the heap every 5 s, and sends at most
 * one datagram per pass on a non-blocking socket, never while the bus is shifting pixels.
 * Messages are queued in a fixed ring (no heap), rate-limited by a token bucket; overflow
 * is counted and reported, never blocks.
 */
#include "wled.h"

#ifndef ARDUINO_ARCH_ESP32
  #error "syslog_events supports ESP32-family targets only"
#endif

#include <WiFiUdp.h>
#include <esp_system.h>
#include <esp_heap_caps.h>
#include <esp_attr.h>
#include <rom/rtc.h>
#include <soc/soc_caps.h>
#include <esp_freertos_hooks.h>

#include "rtc_record.h"

#ifndef SYSLOG_EVENTS_HOST
  #define SYSLOG_EVENTS_HOST ""          // empty = disabled until set in the usermod settings
#endif
#ifndef SYSLOG_EVENTS_PORT
  #define SYSLOG_EVENTS_PORT 514
#endif

#ifdef SYSLOG_EVENTS_PANIC_HOOK
  #include <esp_private/panic_internal.h>
  #include <esp_spi_flash.h>
  #include <soc/soc_memory_types.h>
  #if CONFIG_IDF_TARGET_ARCH_XTENSA
    #include <esp_debug_helpers.h>
    #include <xtensa/xtensa_context.h>
  #endif
#endif

namespace {

// The previous runs as the next boot reports them (rtc_record.h); bump syslogrtc::kMagic if the layout changes.
RTC_NOINIT_ATTR syslogrtc::Record rtcRec;
static_assert(ESP_RST_POWERON == 1 && ESP_RST_SW == 3 && ESP_RST_TASK_WDT == 6 && ESP_RST_SDIO == 10,
              "syslogrtc::resetName indexes esp_reset_reason_t");

// Heartbeats (rtc_record.h): each core's tick interrupt, core 0's idle task, the task watchdog's interrupt.
void IRAM_ATTR tickCpu0() { syslogrtc::tick(rtcRec, 0); }
#if SOC_CPU_CORES_NUM > 1
void IRAM_ATTR tickCpu1() { syslogrtc::tick(rtcRec, 1); }
#endif
bool idleCpu0() {
  syslogrtc::idle0(rtcRec);
  return true;
}

int rtcReason1() {
#if SOC_CPU_CORES_NUM > 1
  return (int)rtc_get_reset_reason(1);
#else
  return -1;
#endif
}

// A global constructor, so the run that ended is in the ring before any code of this run (a panic too) writes.
struct RtcBoot {
  bool kept;
  RtcBoot() : kept(syslogrtc::boot(rtcRec, (uint8_t)rtc_get_reset_reason(0), (uint8_t)rtcReason1())) {}
} rtcBoot;

// Set from other tasks (Wi-Fi event task, async web server); word-sized, read in loop().
volatile uint32_t wifiLostAt = 0, wifiDrops = 0, wifiReason = 0;
volatile uint8_t  otaEvent = 0;   // 1 = upload started, 2 = upload failed
// presetToApply is file-static in WLED, so the id behind ERR_FS_PLOAD is only knowable for JSON requests.
volatile int16_t  lastPresetReq = 0;
volatile uint32_t lastPresetReqAt = 0;
// The JSON request that carried "lor": its buffer-lock id names the path (websocket, HTTP, MQTT, preset ...).
volatile uint8_t  lorReqSrc = 0;
volatile uint32_t lorReqAt = 0;

// Same caps as WLED's getFreeHeapSize(); ESP.getMinFreeHeap() counts more and reads above it.
inline size_t minFreeHeap() { return heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT); }

const char *errName(uint8_t e) {
  switch (e) {
    case ERR_DENIED:      return "permission denied";
    case ERR_CONCURRENCY: return "concurrent client";
    case ERR_NOBUF:       return "JSON buffer busy";
    case ERR_NOT_IMPL:    return "not implemented";
    case ERR_NORAM_PX:    return "no RAM for pixels";
    case ERR_NORAM:       return "effect RAM depleted / heap guard reset";
    case ERR_JSON:        return "JSON parse failed";
    case ERR_FS_BEGIN:    return "filesystem init failed";
    case ERR_FS_QUOTA:    return "filesystem full";
    case ERR_FS_PLOAD:    return "preset does not exist";
    case ERR_FS_IRLOAD:   return "ir.json missing";
    case ERR_FS_RMLOAD:   return "remote.json missing";
    case ERR_FS_GENERAL:  return "filesystem error";
    case ERR_LOW_MEM:     return "low memory";
    case ERR_LOW_SEG_MEM: return "low effect memory";
    case ERR_LOW_WS_MEM:  return "low websocket memory";
    case ERR_LOW_BUF:     return "low pixel buffer memory";
    case ERR_REBOOT_NEEDED:   return "reboot needed";
    case ERR_POWEROFF_NEEDED: return "power cycle needed";
    default:              return "unknown";
  }
}

const char *lorName(uint8_t v) {
  switch (v) {
    case REALTIME_OVERRIDE_NONE: return "off";
    case REALTIME_OVERRIDE_ONCE: return "until live data ends";
    default:                     return "until reboot";
  }
}

const char *lorPath(uint8_t lock) {
  switch (lock) {
    case JSON_LOCK_WS_RECEIVE:  return "via websocket";
    case JSON_LOCK_SERVER:      return "via HTTP JSON";
    case JSON_LOCK_MQTT:        return "via MQTT";
    case JSON_LOCK_NOTIFY:      return "via UDP JSON";
    case JSON_LOCK_PRESET_LOAD: return "via preset";
    case JSON_LOCK_SERIAL:      return "via serial";
    case JSON_LOCK_IR:          return "via IR";
    case JSON_LOCK_REMOTE:      return "via remote";
    default:                    return "via JSON";
  }
}

}  // namespace

#ifdef SYSLOG_EVENTS_PANIC_HOOK
// Linked in with -Wl,--wrap=esp_panic_handler. Runs in panic context, possibly with the
// flash cache off: IRAM only, no flash constants, touches nothing but RTC memory.
extern "C" void __real_esp_panic_handler(panic_info_t *info);

static inline uint32_t IRAM_ATTR stackPc(uint32_t pc) {
  if (pc & 0x80000000) pc = (pc & 0x3fffffff) | 0x40000000;  // strip the window bits of a0
  return pc - 3;  // the call, not the return address — what addr2line wants
}

extern "C" void IRAM_ATTR __wrap_esp_panic_handler(panic_info_t *info) {
  syslogrtc::Crash &c = rtcRec.run.crash;
  c.core = info->core;
  c.exception = info->exception;
  c.exccause = c.excvaddr = 0;
  c.btLen = 0;
  c.reason[0] = 0;
#if CONFIG_IDF_TARGET_ARCH_XTENSA
  const XtExcFrame *f = (const XtExcFrame *)info->frame;
  if (f) {
    c.exccause = f->exccause;
    c.excvaddr = f->excvaddr;
    c.bt[c.btLen++] = f->pc;
    esp_backtrace_frame_t fr = {(uint32_t)f->pc, (uint32_t)f->a1, (uint32_t)f->a0, f};
    // Walking from an insane SP would fault inside the panic handler; IDF checks the same.
    if (esp_stack_ptr_is_sane(fr.sp)) {
      while (c.btLen < syslogrtc::kBt && fr.next_pc) {
        bool ok = esp_backtrace_get_next_frame(&fr);
        c.bt[c.btLen++] = stackPc(fr.pc);
        if (!ok) break;
      }
    }
  }
#else
  c.bt[c.btLen++] = (uint32_t)info->addr;
#endif
  if (info->reason && spi_flash_cache_enabled()) {  // the string lives in flash
    size_t i = 0;
    for (; i < sizeof(c.reason) - 1 && info->reason[i]; i++) c.reason[i] = info->reason[i];
    c.reason[i] = 0;
  }
  rtcRec.run.flags |= syslogrtc::kHasCrash;
  __real_esp_panic_handler(info);
}
#endif

// Called by ESP-IDF's task watchdog interrupt (weak there) before it aborts or, with panic off, carries on.
extern "C" void esp_task_wdt_isr_user_handler(void) {
  const char *t[2] = {nullptr, nullptr};
  for (int c = 0; c < portNUM_PROCESSORS && c < 2; c++) t[c] = pcTaskGetTaskName(xTaskGetCurrentTaskHandleForCPU(c));
  syslogrtc::twdtBeat(rtcRec, t[0], t[1]);
}

class SyslogEvents : public Usermod {
  static constexpr uint8_t  QLEN = 8;
  static constexpr uint16_t LINE = syslogrtc::kLine;
  static constexpr uint8_t  BUCKET = 10;          // burst
  static constexpr uint32_t REFILL_MS = 6000;     // then 10 lines/min sustained
  static constexpr uint32_t SAMPLE_MS = 5000;
  static constexpr uint32_t SETTLE_MS = 3000;     // after (re)connect: let ARP to the gateway resolve,
                                                  // or lwIP keeps only the last queued datagram
  static const char _name[];

  struct Msg { uint8_t sev; char text[LINE]; };
  Msg q[QLEN];
  uint8_t qHead = 0, qCount = 0;
  uint32_t dropped = 0, sent = 0;
  uint8_t tokens = BUCKET;
  uint32_t lastRefill = 0, lastSend = 0, lastSample = 0, lastBeat = 0, connectedAt = 0;
  bool firstConnect = true, reportConnect = false, heapLow = false, initDone = false;
  uint8_t bootLines = 0;  // boot report lines not sent yet; the ring is kept until they are
  uint8_t lastErr = ERR_NONE, lastLor = REALTIME_OVERRIDE_NONE;
  size_t freeHeap = 0, maxBlock = 0;
  int32_t lastRssi = 0;

  WiFiUDP udp;
  IPAddress target;
  bool targetOk = false;
  char hostTag[33] = "";

  // settings
  bool enabled = true;
  String host = SYSLOG_EVENTS_HOST;
  uint16_t port = SYSLOG_EVENTS_PORT;
  String hostname = "";        // empty = the mDNS name: unique per lamp, unlike the server name
  uint16_t beatMin = 60;       // must stay well inside the collector's log-quiet window
  uint16_t heapLowKB = 20;     // largest free block; WLED's own guard acts at MIN_HEAP_SIZE (15 KB)

  __attribute__((format(printf, 3, 4))) void post(uint8_t sev, const char *fmt, ...) {
    if (qCount >= QLEN) { dropped++; return; }
    Msg &m = q[(qHead + qCount) % QLEN];
    m.sev = sev;
    va_list ap; va_start(ap, fmt);
    vsnprintf(m.text, LINE, fmt, ap);
    va_end(ap);
    qCount++;
  }

  void applySettings() {
    targetOk = enabled && port && target.fromString(host);  // IPv4 literal only: a DNS lookup would block the loop
    const char *src = hostname.length() ? hostname.c_str() : cmDNS;
    size_t n = 0;
    for (; src[n] && n < sizeof(hostTag) - 1; n++) {
      char c = src[n];
      hostTag[n] = (isalnum((unsigned char)c) || c == '-' || c == '_' || c == '.') ? c : '-';  // RFC3164 HOSTNAME is one token
    }
    hostTag[n] = 0;
    if (!n) snprintf(hostTag, sizeof(hostTag), "wled-%s", escapedMac.substring(6).c_str());
  }

  void reportBoot() {
    const esp_reset_reason_t r = esp_reset_reason();  // not yet set when rtcBoot was constructed
    const bool unplanned = r != ESP_RST_POWERON && r != ESP_RST_SW && r != ESP_RST_DEEPSLEEP;
    char tail[80];
    syslogrtc::bootTail(rtcRec, rtcBoot.kept, (uint8_t)r, tail, sizeof(tail));
    const uint8_t queued = qCount;
    post(unplanned ? 4 : 5, "boot: reset=%s rtc=%d/%d fw=%s vid=%d rel=%s name=\"%s\"%s", syslogrtc::resetName(r),
         (int)rtc_get_reset_reason(0), rtcReason1(), versionString, VERSION, releaseString, serverDescription, tail);
    syslogrtc::reportLines(rtcRec, [&](int kind, const char *line) {
      post(kind == 1 ? 3 : kind == 2 || unplanned ? 4 : 6, "%s", line);
    });
    bootLines = qCount - queued;
    syslogrtc::startRun(rtcRec);
  }

  void sample(uint32_t now) {
    freeHeap = getFreeHeapSize();
    maxBlock = getContiguousFreeHeap();
    if (WLED_CONNECTED && !wifiLostAt) lastRssi = WiFi.RSSI();  // frozen while a loss is unreported
    const syslogrtc::Crumb c = {now / 1000, freeHeap, maxBlock, minFreeHeap(), lastRssi, WLED_CONNECTED};
    syslogrtc::crumb(rtcRec, c);

    const size_t low = (size_t)heapLowKB * 1024;
    if (!heapLow && maxBlock < low) {
      heapLow = true;
      post(4, "heap: low, largest block %u < %u, free %u, min ever %u", maxBlock, low, freeHeap, c.minHeap);
    } else if (heapLow && maxBlock > low + 4096) {  // hysteresis: one line per crossing, not per sample
      heapLow = false;
      post(5, "heap: recovered, largest block %u, free %u", maxBlock, freeHeap);
    }
  }

  void pollEvents(uint32_t now) {
    uint8_t e = errorFlag;  // cleared by the next /json/state serialisation, so poll every pass
    if (e != lastErr) {
      if (e == ERR_FS_PLOAD && lastPresetReq > 0 && now - lastPresetReqAt < 2000)  // stale id = some other path failed
        post(3, "error: code=%u (%s) requested ps=%d", e, errName(e), lastPresetReq);
      else if (e != ERR_NONE && e != ERR_SYS_REBOOT && e != ERR_SYS_BROWNOUT)  // those two are in the boot line
        post(3, "error: code=%u (%s)", e, errName(e));
      lastPresetReq = 0;
      lastErr = e;
    }
    uint8_t lor = realtimeOverride;
    if (lor != lastLor && !jsonBufferLock) {  // a request still holding the buffer may not have named its path yet
      uint8_t src = lorReqSrc;
      const char *path = src && millis() - lorReqAt < 2000 ? lorPath(src)
                       : lastLor == REALTIME_OVERRIDE_ONCE && !lor && !realtimeMode ? "after live data ended"
                       : "via HTTP API";  // LO=: /win, MQTT/UDP text API, IR/remote/preset macros
      post(lor ? 4 : 5, "live override: %u -> %u (%s) %s", lastLor, lor, lorName(lor), path);
      lorReqSrc = 0;
      lastLor = lor;
    }
    uint8_t o = otaEvent;
    if (o) {
      otaEvent = 0;
      if (o == 1) post(5, "ota: upload started, running %s vid %d", versionString, VERSION);
      else        post(4, "ota: update failed or aborted, still running vid %d", VERSION);
    }
    if (reportConnect && now - connectedAt >= SETTLE_MS && WLED_CONNECTED) {
      reportConnect = false;
      String bssid = WiFi.BSSIDstr();
      if (firstConnect) {
        firstConnect = false;
        post(6, "wifi: connected rssi=%d bssid=%s ch=%d after %us, %u failed attempts",
             WiFi.RSSI(), bssid.c_str(), WiFi.channel(), connectedAt / 1000, wifiDrops);
      } else if (wifiLostAt) {
        post(4, "wifi: reconnected after %us offline, drops=%u last reason=%u (%s), rssi before=%d now=%d bssid=%s ch=%d",
             (connectedAt - wifiLostAt) / 1000, wifiDrops, wifiReason,
             WiFi.disconnectReasonName((wifi_err_reason_t)wifiReason), lastRssi, WiFi.RSSI(), bssid.c_str(), WiFi.channel());
      }
      wifiLostAt = 0;
      wifiDrops = 0;
    }
    if (beatMin && now - lastBeat >= beatMin * 60000UL) {
      lastBeat = now;
      post(6, "status: up=%us heap=%u blk=%u minheap=%u rssi=%d fps=%u on=%d bri=%u ps=%u sent=%u dropped=%u lor=%u",
           (unsigned)(now / 1000), freeHeap, maxBlock, minFreeHeap(), lastRssi, strip.getFps(), bri > 0, bri, currentPreset, sent, dropped,
           realtimeOverride);
    }
  }

  void trySend(uint32_t now) {
    if (now - lastRefill >= REFILL_MS) { lastRefill = now; if (tokens < BUCKET) tokens++; }
    if (!qCount || !tokens || !targetOk || !WLED_CONNECTED || now - connectedAt < SETTLE_MS) return;
    if (now - lastSend < 20 || strip.isUpdating()) return;

    static const char months[] = "JanFebMarAprMayJunJulAugSepOctNovDec";
    const Msg &m = q[qHead];
    char pkt[LINE + 80];
    // Timestamp is local wall time (1970 without NTP); the collector stamps arrival time anyway.
    int n = snprintf(pkt, sizeof(pkt), "<%u>%.3s %2d %02d:%02d:%02d %s wled: %s",
                     16 * 8 + m.sev, months + 3 * (month(localTime) - 1), day(localTime),
                     hour(localTime), minute(localTime), second(localTime), hostTag, m.text);
    lastSend = now;
    if (n <= 0 || !udp.beginPacket(target, port)) return;
    udp.write((const uint8_t *)pkt, min((size_t)n, sizeof(pkt) - 1));
    if (!udp.endPacket()) return;  // lwIP out of buffers: keep the line, retry next pass
    qHead = (qHead + 1) % QLEN;
    qCount--;
    tokens--;
    sent++;
    if (bootLines && !--bootLines) syslogrtc::reported(rtcRec);  // a boot that dies before this is reported next time
    if (dropped && qCount < QLEN) { post(4, "syslog: dropped %u lines (queue full)", dropped); dropped = 0; }
  }

 public:
  void setup() override {
    esp_register_freertos_tick_hook_for_cpu(tickCpu0, 0);
#if SOC_CPU_CORES_NUM > 1
    esp_register_freertos_tick_hook_for_cpu(tickCpu1, 1);
#endif
    esp_register_freertos_idle_hook_for_cpu(idleCpu0, 0);
    WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) {
      if (!wifiLostAt) wifiLostAt = millis() | 1;
      wifiReason = info.wifi_sta_disconnected.reason;
      wifiDrops = wifiDrops + 1;
    }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    applySettings();
    reportBoot();
    lastBeat = lastRefill = millis();
    initDone = true;
  }

  void connected() override {
    connectedAt = millis();
    reportConnect = true;
    syslogrtc::connected(rtcRec);
  }

  void loop() override {
    if (!initDone) return;
    syslogrtc::loopBeat(rtcRec, xPortGetCoreID());
    if (!enabled) return;
    uint32_t now = millis();
    if (now - lastSample >= SAMPLE_MS && !strip.isUpdating()) { lastSample = now; sample(now); }
    pollEvents(now);
    trySend(now);
  }

  void onUpdateBegin(bool init) override {
    rtcRec.otaFromVid = init ? VERSION : 0;
    otaEvent = init ? 1 : 2;
  }

  void readFromJsonState(JsonObject &root) override {
    JsonVariant ps = root["ps"];
    if (ps.is<int>()) { lastPresetReq = ps.as<int>(); lastPresetReqAt = millis(); }  // "1~5~" cycling strings are not ids
    if (!root["lor"].isNull()) { uint8_t l = jsonBufferLock; lorReqAt = millis(); lorReqSrc = l ? l : JSON_LOCK_UNKNOWN; }
  }

  void addToJsonInfo(JsonObject &root) override {
    JsonObject user = root["u"];
    if (user.isNull()) user = root.createNestedObject("u");
    JsonArray row = user.createNestedArray(FPSTR(_name));
    if (!targetOk) { row.add(F("off")); return; }
    row.add(String(hostTag) + " -> " + host + ":" + port);
    row.add(String(F(" sent ")) + sent + F(", dropped ") + dropped);
  }

  void addToConfig(JsonObject &root) override {
    JsonObject top = root.createNestedObject(FPSTR(_name));
    top[F("enabled")] = enabled;
    top[F("host")] = host;
    top[F("port")] = port;
    top[F("hostname")] = hostname;
    top[F("heartbeat-min")] = beatMin;
    top[F("heap-low-kb")] = heapLowKB;
  }

  bool readFromConfig(JsonObject &root) override {
    JsonObject top = root[FPSTR(_name)];
    bool complete = !top.isNull();
    complete &= getJsonValue(top[F("enabled")], enabled, true);
    complete &= getJsonValue(top[F("host")], host, F(SYSLOG_EVENTS_HOST));
    complete &= getJsonValue(top[F("port")], port, SYSLOG_EVENTS_PORT);
    complete &= getJsonValue(top[F("hostname")], hostname, F(""));
    complete &= getJsonValue(top[F("heartbeat-min")], beatMin, 60);
    complete &= getJsonValue(top[F("heap-low-kb")], heapLowKB, 20);
    if (initDone) applySettings();
    return complete;
  }

  void appendConfigData(Print &ui) override {
    ui.print(F("addInfo('Syslog:host',1,'IPv4 address (no DNS: a lookup would stall the LEDs)');"));
    ui.print(F("addInfo('Syslog:hostname',1,'empty = mDNS name');"));
    ui.print(F("addInfo('Syslog:heartbeat-min',1,'minutes, 0 = off');"));
    ui.print(F("addInfo('Syslog:heap-low-kb',1,'warn when the largest free block drops below');"));
  }
};

const char SyslogEvents::_name[] PROGMEM = "Syslog";

static SyslogEvents syslog_events;
REGISTER_USERMOD(syslog_events);
