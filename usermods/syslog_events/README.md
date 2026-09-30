# syslog_events — WLED events as RFC3164 syslog

WLED 16 has no syslog. Its only remote log is the compile-time `WLED_DEBUG` +
`WLED_DEBUG_HOST` stream (raw UDP, not syslog-framed), and a debug build costs
frame rate. This usermod sends the events worth keeping from a normal build as
RFC3164 lines over UDP:

| Line                                                                                                | Severity                     | When                                                                |
| --------------------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------------------------------- |
| `boot: reset=<REASON> rtc=<core0>/<core1> fw=… vid=… rel=… name="…" [after OTA from vid N]`         | notice, warning if unplanned | every boot                                                          |
| `boot: previous run up=… heap=… blk=… minheap=… rssi=… wifi=…`                                      | info, warning if unplanned   | any boot but power-on: the last 5 s breadcrumb before the reset     |
| `crash: core=… exception=… cause=… vaddr=… reason="…" bt=…`                                         | err                          | after a panic, abort or watchdog, with the panic hook built in      |
| `wifi: connected …` / `wifi: reconnected after Ns offline, drops=… last reason=… rssi before/now …` | info / warning               | first connect / every reconnect                                     |
| `heap: low …` / `heap: recovered …`                                                                 | warning / notice             | largest free block crosses `heap-low-kb` (4 KB hysteresis)          |
| `ota: upload started …` / `ota: update failed or aborted …`                                         | notice / warning             | web `/update`                                                       |
| `error: code=N (…) preset=…`                                                                        | err                          | WLED `errorFlag` (missing preset, FS, JSON, RAM, heap-guard resets) |
| `status: up=… heap=… blk=… minheap=… rssi=… fps=… on=… bri=… ps=… sent=… dropped=…`                 | info                         | every `heartbeat-min` (60)                                          |
| `syslog: dropped N lines`                                                                           | warning                      | after the queue overflowed                                          |

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

## Settings (`um.Syslog` in cfg.json, or the Usermods page)

`enabled`, `host` (IPv4 literal: a DNS lookup would block the loop), `port`,
`hostname`, `heartbeat-min` (0 = off), `heap-low-kb`. Build-time defaults:
`SYSLOG_EVENTS_HOST` (empty = off) and `SYSLOG_EVENTS_PORT` (514).

## What it cannot see

- UDP delivery is not confirmed; a lost datagram is lost.
- Playlist load failures return silently in WLED and never set `errorFlag`.
  `errorFlag` itself is cleared by the next `/json/state` read, so a busy UI can
  hide a code between two loop passes.
- ArduinoOTA uploads block the loop and never call the usermod hook; they show
  up only as `reset=SW` on the next boot.
- ESP32 family only.
