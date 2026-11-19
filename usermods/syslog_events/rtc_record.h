// syslog_events' record in RTC slow memory, apart from WLED so tests/test_syslog_rtc.py runs it on the host.
// The bytes survive panics, watchdogs and software resets, not power loss: the magic tells the next boot which
// ("rtcmem=kept|lost"). Each boot moves the run that ended into a ring that is emptied only once the boot's lines
// were sent, so a boot that dies before Wi-Fi is reported by the next one. Heartbeats count each core's ticks from
// setup; no clock survives a reset, so a boot reports each as its distance to the newest count (README).
#pragma once

#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace syslogrtc {

constexpr uint32_t kMagic = 0x53595232;  // "SYR2"
constexpr uint8_t kRing = 4;
constexpr uint8_t kBt = 8;
constexpr size_t kLine = 232;

enum Stage : uint8_t { kNone = 0, kSetup = 1, kLoop = 2, kWifi = 3 };
enum : uint8_t { kHasCrumb = 1, kHasCrash = 2 };

struct Crumb {
  uint32_t upSec, freeHeap, maxBlock, minHeap;
  int32_t rssi, wifiUp;
};

struct Beats {
  uint32_t cpu[2], loop, idle0, twdt;
  char task[2][12];
  uint8_t stage;
};

struct Crash {
  uint32_t core, exception, exccause, excvaddr, btLen;
  uint32_t bt[kBt];
  char reason[40];
};

struct Boot {  // a reset (rtc0, rtc1, reason) and the run that ended with it
  uint8_t rtc0, rtc1, reason, flags;
  Crumb crumb;
  Beats beats;
  Crash crash;
};

struct Run {
  uint8_t flags;
  Crumb crumb;
  Beats beats;
  Crash crash;
};

struct Record {
  uint32_t magic, magicInv;
  uint32_t boots, dropped;  // boots since the record was new; unreported boots pushed out of the ring
  uint32_t otaFromVid;
  uint8_t head, count;
  Boot ring[kRing];
  Run run;
};

// Before anything of this run writes: false if the bytes are not ours (power loss); the record starts new then.
inline bool adopt(Record &r) {
  if (r.magic == kMagic && r.magicInv == ~kMagic && r.count <= kRing && r.head < kRing) return true;
  memset(&r, 0, sizeof r);
  r.magic = kMagic;
  r.magicInv = ~kMagic;
  return false;
}

inline void onBoot(Record &r, uint8_t rtc0, uint8_t rtc1) {  // the run that ended joins the ring
  if (r.count == kRing) {
    r.head = (r.head + 1) % kRing;
    r.count--;
    r.dropped++;
  }
  Boot &b = r.ring[(r.head + r.count) % kRing];
  b.rtc0 = rtc0;
  b.rtc1 = rtc1;
  b.reason = 0;
  b.flags = r.run.flags;
  b.crumb = r.run.crumb;
  b.beats = r.run.beats;
  b.crash = r.run.crash;
  r.count++;
  r.boots++;
  memset(&r.run, 0, sizeof r.run);
}

inline Boot &newest(Record &r) { return r.ring[(r.head + r.count - 1) % kRing]; }

// At boot, from a global constructor: true if the record was kept.
inline bool boot(Record &r, uint8_t rtc0, uint8_t rtc1) {
  const bool kept = adopt(r);
  onBoot(r, rtc0, rtc1);
  return kept;
}

inline void reported(Record &r) {
  r.count = 0;
  r.dropped = 0;
}

// What the usermod's hooks write while the run lasts.
inline void startRun(Record &r) { r.run.beats.stage = kSetup; }
inline void connected(Record &r) { r.run.beats.stage = kWifi; }
// Inlined: the usermod calls it from a tick hook in IRAM, which runs while the flash cache is off.
__attribute__((always_inline)) inline void tick(Record &r, int core) { r.run.beats.cpu[core]++; }
inline void idle0(Record &r) { r.run.beats.idle0 = r.run.beats.cpu[0]; }
inline void loopBeat(Record &r, int core) {
  r.run.beats.loop = r.run.beats.cpu[core];
  if (r.run.beats.stage == kSetup) r.run.beats.stage = kLoop;
}
inline void twdtBeat(Record &r, const char *task0, const char *task1) {
  Beats &b = r.run.beats;
  b.twdt = b.cpu[0] ? b.cpu[0] : 1;
  const char *t[2] = {task0, task1};
  for (int c = 0; c < 2; c++) {
    size_t i = 0;
    for (; t[c] && t[c][i] && i < sizeof b.task[c] - 1; i++) b.task[c][i] = t[c][i];
    b.task[c][i] = 0;
  }
}
inline void crumb(Record &r, const Crumb &c) {
  r.run.crumb = c;
  r.run.flags |= kHasCrumb;
}

// esp_reset_reason_t by value (ESP-IDF 4.4 esp_system.h; syslog_events.cpp asserts the values).
inline const char *resetName(uint8_t r) {
  static const char *const n[] = {"UNKNOWN", "POWERON", "EXT", "SW", "PANIC", "INT_WDT",
                                  "TASK_WDT", "WDT", "DEEPSLEEP", "BROWNOUT", "SDIO"};
  return r < sizeof n / sizeof n[0] ? n[r] : "UNKNOWN";
}

inline const char *stageName(uint8_t s) {
  static const char *const n[] = {"none", "setup", "loop", "wifi"};
  return s < 4 ? n[s] : "?";
}

inline const char *excName(uint32_t e) {
  static const char *const n[] = {"DEBUG", "IWDT", "TWDT", "ABORT", "FAULT"};
  return e < 5 ? n[e] : "?";
}

// Appends with snprintf; a full buffer stays full.
struct Out {
  char *p;
  size_t len, n;
  Out(char *out, size_t size) : p(out), len(size), n(0) {
    if (len) p[0] = 0;
  }
  __attribute__((format(printf, 2, 3))) void add(const char *fmt, ...) {
    if (n >= len) return;
    va_list ap;
    va_start(ap, fmt);
    const int k = vsnprintf(p + n, len - n, fmt, ap);
    va_end(ap);
    if (k > 0) n = n + size_t(k) < len ? n + size_t(k) : len;
  }
};

// The run's breadcrumb (full: as the line had before, else uptime and Wi-Fi), stage, and how long before the newest
// tick each heartbeat was last seen ("ago_ms").
inline void addRun(Out &o, const Boot &b, bool full) {
  const Crumb &c = b.crumb;
  if ((b.flags & kHasCrumb) && full)
    o.add(" up=%us heap=%u blk=%u minheap=%u rssi=%d wifi=%s", unsigned(c.upSec), unsigned(c.freeHeap),
          unsigned(c.maxBlock), unsigned(c.minHeap), int(c.rssi), c.wifiUp ? "up" : "down");
  else if (b.flags & kHasCrumb)
    o.add(" up=%us wifi=%s", unsigned(c.upSec), c.wifiUp ? "up" : "down");
  const Beats &t = b.beats;
  o.add(" stage=%s", stageName(t.stage));
  const uint32_t end = t.cpu[0] > t.cpu[1] ? t.cpu[0] : t.cpu[1];
  if (!end) return;
  o.add(" ago_ms cpu0=%u cpu1=%u loop=%u idle0=%u", unsigned(end - t.cpu[0]), unsigned(end - t.cpu[1]),
        unsigned(end - t.loop), unsigned(end - t.idle0));
  if (t.twdt) o.add(" twdt=%u tasks=\"%.11s\"/\"%.11s\"", unsigned(end - t.twdt), t.task[0], t.task[1]);
}

// "[ after OTA from vid V] rtcmem=kept boots=N[ unreported=K]", the end of the boot line; sets this boot's reason.
inline void bootTail(Record &r, bool kept, uint8_t reason, char *out, size_t len) {
  newest(r).reason = reason;
  Out o{out, len};
  if (r.otaFromVid && reason == 3) o.add(" after OTA from vid %u", unsigned(r.otaFromVid));
  r.otaFromVid = 0;
  o.add(" rtcmem=%s boots=%u", kept ? "kept" : "lost", unsigned(r.boots));
  if (r.count > 1 || r.dropped) o.add(" unreported=%u", unsigned(r.count - 1 + r.dropped));
}

// The lines after the boot line, each passed to emit(kind, text): 0 this boot's previous run, 1 its crash, 2 an
// earlier boot that was never reported.
template <typename F> void reportLines(const Record &r, F emit) {
  char line[kLine];
  const Boot &b = r.ring[(r.head + r.count - 1) % kRing];
  if ((b.flags & kHasCrumb) || b.beats.stage) {
    Out o{line, kLine};
    o.add("boot: previous run");
    addRun(o, b, true);
    emit(0, line);
  }
  if (b.flags & kHasCrash) {
    const Crash &c = b.crash;
    Out o{line, kLine};
    o.add("crash: core=%u exception=%s cause=%u vaddr=0x%08x reason=\"%.39s\" bt=", unsigned(c.core),
          excName(c.exception), unsigned(c.exccause), unsigned(c.excvaddr), c.reason);
    for (uint32_t i = 0; i < c.btLen && i < kBt; i++) o.add(i ? " 0x%08x" : "0x%08x", unsigned(c.bt[i]));
    if (!c.btLen) o.add("-");
    emit(1, line);
  }
  for (uint8_t i = 0; i + 1 < r.count; i++) {
    const Boot &e = r.ring[(r.head + i) % kRing];
    Out o{line, kLine};
    o.add("boot: earlier boot %u/%u reset=%s rtc=%u/%u, run before:", unsigned(i + 1), unsigned(r.count - 1),
          resetName(e.reason), unsigned(e.rtc0), unsigned(e.rtc1));
    addRun(o, e, false);
    if (e.flags & kHasCrash) o.add(" crash=%s pc=0x%08x", excName(e.crash.exception), unsigned(e.crash.bt[0]));
    emit(2, line);
  }
}

}  // namespace syslogrtc
