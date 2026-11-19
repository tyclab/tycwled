"""usermods/syslog_events: the record in RTC memory that the next boot reports (rtc_record.h).

The scenario tests compile tests/syslog_rtc_host.cpp, which makes the calls syslog_events.cpp makes at each event, and
read the lines a boot would send, built as C++11 as the lamps' Arduino core builds it. They skip without a C++ compiler.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UM = os.path.join(ROOT, "usermods", "syslog_events")
CPP = open(os.path.join(UM, "syslog_events.cpp")).read()
HOST = os.path.join(ROOT, "tests", "syslog_rtc_host.cpp")
CXX = shutil.which("g++") or shutil.which("c++") or shutil.which("clang++")
LINE = int(re.search(r"constexpr size_t kLine = (\d+);", open(os.path.join(UM, "rtc_record.h")).read()).group(1))
QLEN = int(re.search(r"QLEN = (\d+);", CPP).group(1))

# A run of 2806 s with Wi-Fi up, every heartbeat alive to the end.
LONG_RUN = ["crumb 2806 76000 51000 16000 -39 1", "ticks 2806000 2806000", "idle0", "loop", "wifi"]
FIRST_BOOT = ["boot 1 14 1", "sent"]


@unittest.skipUnless(CXX, "no C++ compiler")
class Scenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.exe = os.path.join(cls.tmp, "syslog_rtc_host")
        subprocess.run([CXX, "-std=gnu++11", "-O1", "-Wall", "-Wextra", "-Wformat=2", "-Werror", "-o", cls.exe, HOST], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp)

    def boots(self, *script):
        """Every boot's lines, as lists: [boot line, following lines...]."""
        out = subprocess.run([self.exe], input="\n".join(script) + "\n", capture_output=True, text=True, check=True)
        boots = []
        for line in out.stdout.splitlines():
            if line.startswith("boot: reset="):
                boots.append([line])
            elif re.match(r"\d\|", line):
                boots[-1].append(line[2:])
        for b in boots:
            self.assertLessEqual(len(b), QLEN, "a boot's lines must fit the send queue")
            for line in b:
                self.assertLess(len(line), LINE, line)
        return boots

    def test_power_loss_is_told_apart_from_a_reset_that_kept_the_record(self):
        lost = self.boots(*FIRST_BOOT, *LONG_RUN, "power", "boot 7 14 6")[-1]
        self.assertEqual(lost, ["boot: reset=TASK_WDT rtc=7/14 rtcmem=lost boots=1"])
        kept = self.boots(*FIRST_BOOT, *LONG_RUN, "boot 7 14 6")[-1]
        self.assertEqual(kept[0], "boot: reset=TASK_WDT rtc=7/14 rtcmem=kept boots=2")
        self.assertEqual(kept[1], "boot: previous run up=2806s heap=76000 blk=51000 minheap=16000 rssi=-39 wifi=up "
                                  "stage=wifi ago_ms cpu0=0 cpu1=0 loop=0 idle0=0")

    def test_a_boot_that_died_before_its_lines_went_out_is_reported_by_the_next(self):
        # The long run ends in a task watchdog panic; the boot after it hangs in setup with core 0's idle task
        # starved until the watchdog's second stage resets the chip.
        b = self.boots(*FIRST_BOOT, *LONG_RUN, "twdt IDLE0 loopTask", "crash 2 400d1234", "boot 12 12 6",
                       "ticks 30000 30000", "twdt wifi loopTask", "boot 7 14 6")[-1]
        self.assertEqual(b, [
            "boot: reset=TASK_WDT rtc=7/14 rtcmem=kept boots=3 unreported=1",
            "boot: previous run stage=setup ago_ms cpu0=0 cpu1=0 loop=30000 idle0=30000 twdt=0 "
            'tasks="wifi"/"loopTask"',
            "boot: earlier boot 1/1 reset=TASK_WDT rtc=12/12, run before: up=2806s wifi=up stage=wifi ago_ms "
            'cpu0=0 cpu1=0 loop=0 idle0=0 twdt=0 tasks="IDLE0"/"loopTask" crash=TWDT pc=0x400d1234',
        ])

    def test_lines_that_went_out_are_not_repeated(self):
        b = self.boots(*FIRST_BOOT, *LONG_RUN, "boot 7 14 6", "sent", "ticks 5 5", "loop", "boot 12 12 3")[-1]
        self.assertEqual(b, ["boot: reset=SW rtc=12/12 rtcmem=kept boots=3",
                             "boot: previous run stage=loop ago_ms cpu0=0 cpu1=0 loop=0 idle0=5"])

    def test_the_ring_keeps_the_newest_boots_and_counts_the_rest(self):
        b = self.boots(*FIRST_BOOT, *["boot 7 14 6"] * 5, "boot 9 14 7")[-1]
        self.assertEqual(b[0], "boot: reset=WDT rtc=9/14 rtcmem=kept boots=7 unreported=5")
        self.assertEqual([line.split(",")[0] for line in b[2:]],
                         ["boot: earlier boot %d/3 reset=TASK_WDT rtc=7/14" % i for i in (1, 2, 3)])

    def test_heartbeats_tell_which_part_stopped_first(self):
        starved = self.boots(*FIRST_BOOT, "ticks 5000 5000", "idle0", "loop", "ticks 30000 30000", "loop",
                             "boot 7 14 6")[-1][1]
        self.assertTrue(starved.endswith("stage=loop ago_ms cpu0=0 cpu1=0 loop=0 idle0=30000"), starved)
        core1 = self.boots(*FIRST_BOOT, "ticks 5000 5000", "idle0", "loop", "ticks 2000 0", "idle0",
                           "boot 8 14 5")[-1][1]
        self.assertTrue(core1.endswith("ago_ms cpu0=0 cpu1=2000 loop=2000 idle0=0"), core1)

    def test_ota_suffix_only_on_the_software_reset_that_followed_the_upload(self):
        self.assertEqual(self.boots(*FIRST_BOOT, "ota 2611181", "boot 12 12 3")[-1][0],
                         "boot: reset=SW rtc=12/12 after OTA from vid 2611181 rtcmem=kept boots=2")
        self.assertEqual(self.boots(*FIRST_BOOT, "ota 2611181", "boot 7 14 6", "boot 12 12 3")[-1][0],
                         "boot: reset=SW rtc=12/12 rtcmem=kept boots=3 unreported=1")

    def test_record_fits_rtc_slow_memory(self):
        size = int(subprocess.run([self.exe], input="size\n", capture_output=True, text=True).stdout.split()[1])
        self.assertLessEqual(size, 1024)


class Glue(unittest.TestCase):
    """syslog_events.cpp makes the calls the scenarios make."""

    def test_record_is_taken_over_in_a_global_constructor(self):
        self.assertRegex(CPP, r"RtcBoot\(\) : kept\(syslogrtc::boot\(rtcRec, ")
        self.assertRegex(CPP, r"\} rtcBoot;")

    def test_heartbeat_hooks(self):
        self.assertRegex(CPP, r"void IRAM_ATTR tickCpu0\(\) \{ syslogrtc::tick\(rtcRec, 0\); \}")
        self.assertRegex(CPP, r"esp_register_freertos_tick_hook_for_cpu\(tickCpu0, 0\)")
        self.assertRegex(CPP, r"esp_register_freertos_tick_hook_for_cpu\(tickCpu1, 1\)")
        self.assertRegex(CPP, r"esp_register_freertos_idle_hook_for_cpu\(idleCpu0, 0\)")
        self.assertRegex(CPP, r'extern "C" void esp_task_wdt_isr_user_handler\(void\)')
        self.assertRegex(CPP, r"syslogrtc::loopBeat\(rtcRec, xPortGetCoreID\(\)\)")
        self.assertRegex(CPP, r"syslogrtc::connected\(rtcRec\)")
        self.assertRegex(CPP, r"syslogrtc::crumb\(rtcRec, c\)")

    def test_ring_is_cleared_only_after_the_boot_lines_were_sent(self):
        send = CPP[CPP.index("void trySend("):CPP.index("public:")]
        self.assertLess(send.index("if (!udp.endPacket()) return;"), send.index("syslogrtc::reported(rtcRec)"))
        self.assertEqual(CPP.count("syslogrtc::reported("), 1)


if __name__ == "__main__":
    unittest.main()
