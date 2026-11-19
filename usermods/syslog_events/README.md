# syslog_events — WLED events as RFC3164 syslog

WLED 16 has no syslog. Its only remote log is the compile-time `WLED_DEBUG` +
`WLED_DEBUG_HOST` stream (raw UDP, not syslog-framed), and a debug build costs
frame rate. This usermod sends the events worth keeping from a normal build as
RFC3164 lines over UDP:

| Line                                                                                                                                 | Severity                     | When                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------- | -------------------------------------------------------------------- |
| `boot: reset=<REASON> rtc=<core0>/<core1> fw=… vid=… rel=… name="…" [after OTA from vid N] rtcmem=kept\|lost boots=N [unreported=K]` | notice, warning if unplanned | every boot                                                           |
| `boot: previous run up=… heap=… blk=… minheap=… rssi=… wifi=… stage=… ago_ms cpu0=… cpu1=… loop=… idle0=… [twdt=… tasks="…"/"…"]`    | info, warning if unplanned   | when the record was kept: the last 5 s breadcrumb and the heartbeats |
| `crash: core=… exception=… cause=… vaddr=… reason="…" bt=…`                                                                          | err                          | after a panic, abort or watchdog, with the panic hook built in       |
| `boot: earlier boot i/N reset=… rtc=…, run before: up=… wifi=… stage=… ago_ms … [crash=… pc=…]`                                      | warning                      | per boot whose own lines never went out (it died before Wi-Fi)       |
| `wifi: connected …` / `wifi: reconnected after Ns offline, drops=… last reason=… rssi before/now …`                                  | info / warning               | first connect / every reconnect                                      |
| `heap: low …` / `heap: recovered …`                                                                                                  | warning / notice             | largest free block crosses `heap-low-kb` (4 KB hysteresis)           |
| `ota: upload started …` / `ota: update failed or aborted …`                                                                          | notice / warning             | web `/update`                                                        |
| `error: code=N (…) [requested ps=N]`                                                                                                 | err                          | WLED `errorFlag` (missing preset, FS, JSON, RAM, heap-guard resets)  |
| `live override: <old> -> <new> (<mode>) <path>`                                                                                      | warning, notice when cleared | every change of WLED's live override (`lor`)                         |
| `status: up=… heap=… blk=… minheap=… rssi=… fps=… on=… bri=… ps=… sent=… dropped=… lor=…`                                            | info                         | every `heartbeat-min` (60)                                           |
| `syslog: dropped N lines`                                                                                                            | warning                      | after the queue overflowed                                           |

The HOSTNAME is the mDNS name unless `hostname` is set: server names are free
text and two lamps may share one, while a log collector keys streams on this
field. The tag is `wled`.

## Cost to the LEDs

`loop()` does constant work per pass. Heap and RSSI are sampled every 5 s.
At most one datagram goes out per pass, on WiFiUDP's non-blocking socket, and
never while the bus is shifting pixels (`strip.isUpdating()`), which is when
RMT refills can be delayed by network interrupts. Lines wait in a fixed 8-slot
ring (no heap), limited by a token bucket (burst 10, then one line per 6 s).
The first send waits 3 s after each (re)connect, so ARP for the gateway has
resolved; otherwise lwIP keeps only the last datagram it queued.

## Crash record

Build with `-D SYSLOG_EVENTS_PANIC_HOOK -Wl,--wrap=esp_panic_handler` (both,
or neither). The wrapper runs in panic context from IRAM and writes core,
exception, `EXCCAUSE`/`EXCVADDR`, the reason string and up to 8 backtrace PCs
into RTC memory, then hands over to ESP-IDF's own handler. The next boot sends
it. Decode the `bt=` addresses with the ELF of that exact build:
`xtensa-esp32-elf-addr2line -pfiaC -e firmware.elf <addresses>` (`xtensa-esp32s3-…` on an S3).

RTC memory survives panics, watchdogs, software resets and usually brownouts. It
does not survive power loss. After a power-on, only the reset reason is reported.

## Record in RTC memory (`rtc_record.h`)

- `rtcmem=lost`: the record's magic was not there, so power was lost (or the chip
  held in reset) since the last boot, whatever `reset=` says: a `TASK_WDT rtc=7`
  with `rtcmem=lost` is the boot ROM's flash-boot watchdog after a power cut, not
  the task watchdog of a running image. `rtcmem=kept` with `POWERON` is a dip
  short enough to keep RTC memory.
- `boots=N` counts boots since the record was new. A boot keeps its lines in the
  record until they were sent; one that dies before Wi-Fi is reported by the next
  boot as `boot: earlier boot …` and counted in `unreported=` (the record holds
  four; older ones are only counted).
- `stage=` is how far the run got: `setup`, `loop` (main loop ran), `wifi`.
- Heartbeats count FreeRTOS ticks from setup: `cpu0`/`cpu1` each core's tick
  interrupt, `loop` the main loop, `idle0` core 0's idle task (what the task
  watchdog watches), `twdt` its interrupt, with the tasks running on each core
  then. `ago_ms` gives each as ms before the newest tick: `cpu0=0 idle0=10000`
  is core 0's idle task starved for its last 10 s; all near 0 is a stop of the
  whole chip.

## Settings (`um.Syslog` in cfg.json, or the Usermods page)

`enabled`, `host` (IPv4 literal: a DNS lookup would block the loop), `port`,
`hostname`, `heartbeat-min` (0 = off), `heap-low-kb`. Build-time defaults:
`SYSLOG_EVENTS_HOST` (empty = off) and `SYSLOG_EVENTS_PORT` (514).

## What it cannot see

- UDP delivery is not confirmed; a lost datagram is lost.
- Playlist load failures return silently in WLED and never set `errorFlag`. A
  missing preset names its id only when it was requested over the JSON API;
  playlists, buttons and timers apply presets without one.
  `errorFlag` itself is cleared by the next `/json/state` read, so a busy UI can
  hide a code between two loop passes.
- A live-override line names the path, not the client: `via websocket`
  (the WLED web UI while its socket is open), `via HTTP JSON`, `via MQTT`,
  `via preset` and so on for a JSON `lor`, taken from the JSON buffer's lock
  holder within 2 s. `via HTTP API` is an `LO=` command (`/win`, MQTT or UDP
  text API, IR, remote or preset macros); `after live data ended` is WLED
  clearing "once" when the stream stops. The client IP is not available.
- ArduinoOTA uploads block the loop and never call the usermod hook; they show
  up only as `reset=SW` on the next boot.
- ESP32 family only.
