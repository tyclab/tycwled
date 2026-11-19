// Runs usermods/syslog_events/rtc_record.h on the host for tests/test_syslog_rtc.py: reads one command per line on
// stdin and makes the calls syslog_events.cpp makes at that event; prints every line a boot would send.
//   power                        RTC bytes lost (filled with a pattern, as after power-on)
//   boot RTC0 RTC1 REASON        global constructor, then reportBoot (REASON: esp_reset_reason_t value)
//   sent                         the boot's lines went out
//   crumb UP HEAP BLK MIN RSSI W sample()
//   ticks N0 N1                  N0 tick interrupts on core 0, N1 on core 1
//   idle0 | loop | wifi          core 0's idle hook, a main loop pass on core 1, connected()
//   twdt TASK0 TASK1             the task watchdog's interrupt
//   crash EXC PC                 the panic hook
//   ota VID                      onUpdateBegin(true)
//   size                         sizeof the record
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <sstream>
#include <string>

#include "../usermods/syslog_events/rtc_record.h"

static syslogrtc::Record rec;

int main() {
  memset(&rec, 0xa5, sizeof rec);
  bool kept = false;
  std::string cmdline;
  while (std::getline(std::cin, cmdline)) {
    std::istringstream in(cmdline);
    std::string cmd;
    in >> cmd;
    if (cmd == "power") {
      memset(&rec, 0x5a, sizeof rec);
    } else if (cmd == "boot") {
      unsigned rtc0, rtc1, reason;
      in >> rtc0 >> rtc1 >> reason;
      kept = syslogrtc::boot(rec, uint8_t(rtc0), uint8_t(rtc1));
      char tail[80];
      syslogrtc::bootTail(rec, kept, uint8_t(reason), tail, sizeof tail);
      printf("boot: reset=%s rtc=%u/%u%s\n", syslogrtc::resetName(uint8_t(reason)), rtc0, rtc1, tail);
      syslogrtc::reportLines(rec, [](int kind, const char *line) { printf("%d|%s\n", kind, line); });
      syslogrtc::startRun(rec);
    } else if (cmd == "sent") {
      syslogrtc::reported(rec);
    } else if (cmd == "crumb") {
      syslogrtc::Crumb c{};
      in >> c.upSec >> c.freeHeap >> c.maxBlock >> c.minHeap >> c.rssi >> c.wifiUp;
      syslogrtc::crumb(rec, c);
    } else if (cmd == "ticks") {
      unsigned n0, n1;
      in >> n0 >> n1;
      for (unsigned i = 0; i < n0; i++) syslogrtc::tick(rec, 0);
      for (unsigned i = 0; i < n1; i++) syslogrtc::tick(rec, 1);
    } else if (cmd == "idle0") {
      syslogrtc::idle0(rec);
    } else if (cmd == "loop") {
      syslogrtc::loopBeat(rec, 1);
    } else if (cmd == "wifi") {
      syslogrtc::connected(rec);
    } else if (cmd == "twdt") {
      std::string a, b;
      in >> a >> b;
      syslogrtc::twdtBeat(rec, a.c_str(), b.c_str());
    } else if (cmd == "crash") {
      unsigned exc, pc;
      in >> exc >> std::hex >> pc;
      syslogrtc::Crash &c = rec.run.crash;
      memset(&c, 0, sizeof c);
      c.exception = exc;
      c.bt[c.btLen++] = pc;
      rec.run.flags |= syslogrtc::kHasCrash;
    } else if (cmd == "ota") {
      in >> rec.otaFromVid;
    } else if (cmd == "size") {
      printf("size %zu\n", sizeof rec);
    } else if (!cmd.empty()) {
      fprintf(stderr, "unknown command %s\n", cmd.c_str());
      return 2;
    }
  }
  return 0;
}
