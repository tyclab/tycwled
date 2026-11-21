"""Raw lamp recordings, device backups and network details stay out of what is published."""
import bz2
from contextlib import chdir
import gzip
import io
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CHECK = ROOT / "tools" / "check_private_lamp_data.py"
sys.path.insert(0, str(CHECK.parent))
import check_private_lamp_data as guard  # noqa: E402

# Shaped like real values and built here, so this file holds none.
MAC = ":".join(["02", "1a", "2b", "3c", "4d", "5e"])
LAN = ".".join(["10", "20", "30", "40"])
ULA = ":".join(["fd12", "3456", "789a", "", "1"])
FRAMES = [[i / 10, ["ff0000", "003300"]] for i in range(12)]
STAMP = dict(ip=LAN, ver="16.0.1", fps=42, wifi=dict(bssid=MAC, rssi=-60, channel=6), state=dict(on=True))
CAPTURE = json.dumps(dict(meta=dict(ref=STAMP, tgt=STAMP), ref=FRAMES, tgt=FRAMES)).encode()
STRUCTURE = json.dumps(dict(ref=FRAMES, tgt=FRAMES)).encode()
CENSUS = json.dumps(dict(meta=STAMP, frames=FRAMES)).encode()
STROBE = json.dumps(dict(meta=dict(maxb=255, phases=[["on", "off"]]), frames=FRAMES)).encode()
BACKUP = json.dumps({"id": dict(mdns="wled-" + MAC.replace(":", "")[6:], name="Lamp"),
                     "nw": dict(ins=[dict(ssid="home network", pskl=12)], linked_remote=[]),
                     "ap": dict(ssid="WLED-AP"), "if": dict(ntp=dict(lt=12.5, ln=34.5))}).encode()
SUMMARY = f"ref {LAN} target {LAN}\npreset  1 PASS\n".encode()
FACTORY = json.dumps({"nw": dict(ins=[dict(ssid="", pskl=0)]), "ap": dict(ssid="WLED-AP"),
                      "if": dict(ntp=dict(lt=0.0, ln=0.0))}).encode()
PATH_ONLY = "a raw capture or device backup"


def purged(path):
    """Content of the kind the purged file at this path held."""
    name = path.rsplit("/", 1)[-1]
    data = (SUMMARY if name.endswith(".log") else BACKUP if name == "cfg.json" else STRUCTURE if name.startswith("struct-")
            else STROBE if name.startswith("strobe-") else CENSUS if "/frames/" in path
            else CAPTURE if name.startswith("verify-") else b'{"map":[0,1]}')
    return gzip.compress(data) if name.endswith(".gz") else data


class Content(unittest.TestCase):
    def test_every_purged_path_is_refused(self):
        paths = (ROOT / "tests" / "purged_paths.txt").read_text().split()
        self.assertEqual(len(paths), 248)
        by_content = 0
        for path in paths:
            self.assertTrue(guard.findings(path, purged(path)), path)
            by_content += bool(guard.findings("renamed/" + path.replace("/", "-") + ".dat", purged(path)))
        # All but the backup's ledmap and presets, which equal the published files, are refused under any name.
        self.assertEqual(by_content, 246)

    def test_a_recording_is_refused_under_any_name_and_compression(self):
        archive, tarball = io.BytesIO(), io.BytesIO()
        with zipfile.ZipFile(archive, "w") as packed:
            packed.writestr("p1.json", gzip.compress(STRUCTURE))
        with tarfile.open(fileobj=tarball, mode="w") as packed:
            member = tarfile.TarInfo("p1.json")
            member.size = len(STRUCTURE)
            packed.addfile(member, io.BytesIO(STRUCTURE))
        for name, data in (("docs/measurement-p1.json", STRUCTURE), ("run1/verify_p1.json.gz.bak", gzip.compress(STRUCTURE)),
                           ("run1/p1.bin", gzip.compress(gzip.compress(STRUCTURE))), ("run1/p1.json.xz", lzma.compress(STRUCTURE)),
                           ("run1/p1.json.bz2", bz2.compress(STRUCTURE)), ("run1/captures.zip", archive.getvalue()),
                           ("run1/evidence.tar.gz", gzip.compress(tarball.getvalue())), ("run1/frames.json", json.dumps(FRAMES).encode())):
            with self.subTest(name=name):
                self.assertEqual(guard.findings(name, data), ["a raw lamp recording"])
        for name, data in (("run1/p1.json.zst", b"\x28\xb5\x2f\xfd" + STRUCTURE), ("run1/p1.json.gz", gzip.compress(STRUCTURE)[:40])):
            with self.subTest(name=name):
                self.assertEqual(guard.findings(name, data), ["compressed data this check cannot read"])

    def test_network_details_are_refused_in_any_file(self):
        for reason, text in (("a MAC address", f"heard {MAC}"), ("a MAC address", json.dumps(dict(mac=MAC.replace(":", "")))),
                             ("a MAC address", f"heard {MAC.replace(':', '-').upper()}"),
                             ("a private network address", f"make verify REF={LAN}"),
                             ("a private network address", "host " + ".".join(["192", "168", "1", "20"])),
                             ("a private network address", "host " + ".".join(["172", "20", "0", "5"])),
                             ("a private network address", f"route {ULA}"),
                             ("a Wi-Fi network name or BSSID", json.dumps(dict(ssid="home network"))),
                             ("a Wi-Fi network name or BSSID", json.dumps(json.dumps(dict(bssid="any")))),
                             ("a location", json.dumps(dict(lt=-12.5))), ("a location", str(dict(ln=7)))):
            for path in ("README.md", "tests/test_example.py", "notes/run.log"):
                with self.subTest(text=text, path=path):
                    self.assertEqual(guard.findings(path, text.encode()), [reason])

    def test_documentation_values_and_ordinary_files_pass(self):
        public = dict(mac="00005e005301", bssid="", ssid="example-network", lt=0, ln=0.0, ip="192.0.2.20",
                      heard=["00:00:5E:00:53:0a", "ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"], gw="198.51.100.1",
                      linked_remote=["00005e00530a"], ap=dict(ssid="WLED-AP"), server="2001:db8::1", public="172.32.0.1")
        for text in (json.dumps(public), str(public), '{"map":[0,1,2]}', json.dumps({"1": {"n": "solid", "seg": [{"id": 0}]}}),
                     "ver 10.0.19041.1 at 12:34:56, sha256 fd12ab34", json.dumps([[0, 1], [2, 3]])):
            with self.subTest(text=text):
                self.assertEqual(guard.findings("fleet/example.json", text.encode()), [])
        self.assertEqual(guard.findings("curtain/squid.gif", b"GIF89a" + bytes(range(256)) * 8), [])

    def test_the_factory_config_is_exempt_by_path_and_checked_by_content(self):
        self.assertEqual(guard.findings(guard.FACTORY_CONFIG, FACTORY), [])
        self.assertEqual(guard.findings("glorb/backup/cfg.json", FACTORY), [PATH_ONLY])
        self.assertEqual(guard.findings(guard.FACTORY_CONFIG, BACKUP),
                         ["a Wi-Fi network name or BSSID", "a location"])

    def test_only_the_collector_define_may_hold_an_address(self):
        define = f'build_flags = -D SYSLOG_EVENTS_HOST=\\"{LAN}\\" -D SYSLOG_EVENTS_PORT=1515\n'.encode()
        self.assertEqual(guard.findings(guard.COLLECTOR_CONFIG, define), [])
        self.assertEqual(guard.findings(guard.COLLECTOR_CONFIG, define + f"; lamp at {LAN}\n".encode()),
                         ["a private network address"])
        self.assertEqual(guard.findings("fleet/other.ini", define), ["a private network address"])

    def test_the_repository_as_checked_out_passes(self):
        with chdir(ROOT):
            self.assertEqual(guard.problems(), [])
            if subprocess.check_output(["git", "rev-parse", "--is-shallow-repository"]).strip() == b"true":
                self.skipTest("a shallow clone cannot show where its history starts")
            self.assertEqual(guard.off_lineage(["HEAD"]), [])


class Published(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PRE_COMMIT"))}
        self.git("init", "--quiet", "--initial-branch", "main")
        self.shared = self.commit("README.md", b"lamps\n")

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                        "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                                        *args], cwd=self.root, env=self.env).strip().decode()

    def commit(self, path, data):
        """Write, or with None remove, one file and commit it."""
        if data is None:
            self.git("rm", "--quiet", path)
        else:
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_bytes(data)
            self.git("add", "--force", path)
        self.git("commit", "--quiet", "-m", path)
        return self.git("rev-parse", "HEAD")

    def check(self, *revs, **env):
        return subprocess.run([sys.executable, CHECK, *revs], cwd=self.root, env={**self.env, **env},
                              capture_output=True, text=True)

    def problems(self, *revs, start):
        with chdir(self.root):
            return guard.problems(list(revs), start)

    def test_staged_recording_is_refused_and_a_file_kept_on_disk_is_not(self):
        (self.root / ".gitignore").write_text("captures/\n")
        capture = self.root / "captures" / "verify-p1.json.gz"
        capture.parent.mkdir()
        capture.write_bytes(gzip.compress(CAPTURE))
        self.git("add", "--force", "captures")
        refused = self.check()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("captures/verify-p1.json.gz: a raw lamp recording", refused.stderr)
        for private in (MAC, LAN):
            self.assertNotIn(private, refused.stderr + refused.stdout)
        self.git("rm", "--cached", "--quiet", "captures/verify-p1.json.gz")
        self.assertTrue(capture.exists())
        self.assertEqual(self.check().returncode, 0)

    def test_a_file_added_and_removed_again_is_refused(self):
        start = self.commit("fleet/README.md", b"fleet\n")
        self.commit("curtain/census/frames/fx000.json.gz", gzip.compress(CENSUS))
        tip = self.commit("curtain/census/frames/fx000.json.gz", None)
        self.assertEqual(self.git("ls-tree", "-r", "--name-only", tip).split(), ["README.md", "fleet/README.md"])
        self.assertEqual(self.problems(f"{start}..{tip}", start=start),
                         [f"curtain/census/frames/fx000.json.gz: {reason}" for reason in
                          ("a MAC address", "a Wi-Fi network name or BSSID", "a private network address", "a raw lamp recording")])
        clean = self.commit("docs/notes.md", b"notes\n")
        self.assertEqual(self.problems(f"{tip}..{clean}", start=start), [])

    def test_a_branch_from_the_history_before_the_rewrite_is_refused(self):
        self.git("checkout", "--quiet", "-b", "before")
        self.commit("captures/verify-p1.json.gz", gzip.compress(CAPTURE))
        old = self.commit("captures/verify-p1.json.gz", None)
        self.git("checkout", "--quiet", "main")
        start = self.commit("fleet/README.md", b"fleet\n")
        new = self.commit("docs/notes.md", b"notes\n")
        self.git("checkout", "--quiet", "-b", "cut-before", old)
        cut = self.commit("docs/fix.md", b"fix\n")
        self.git("checkout", "--quiet", "-b", "merged", new)
        self.git("merge", "--quiet", "--no-edit", cut)
        merged = self.git("rev-parse", "HEAD")
        self.assertEqual(self.problems(f"{start}..{new}", start=start), [])
        for tip in (cut, merged):
            with self.subTest(tip=tip):
                found = self.problems(f"{old}..{tip}", start=start)
                self.assertEqual(len(found), 1)
                self.assertRegex(found[0], "^3 commit.s. come from the history before the recordings were removed")

    def test_a_push_is_checked_from_the_ref_it_names_and_needs_the_rewritten_history(self):
        tip = self.commit("docs/notes.md", b"notes\n")
        for env in ({"PRE_COMMIT_TO_REF": tip, "PRE_COMMIT_FROM_REF": self.shared}, {"PRE_COMMIT_LOCAL_BRANCH": "refs/heads/main"}):
            with self.subTest(env=env):
                refused = self.check(**env)
                self.assertEqual(refused.returncode, 1)
                self.assertIn("The rewritten history is not in this clone", refused.stderr)

    def test_install_hooks_installs_the_push_hook(self):
        plan = subprocess.check_output(["make", "--dry-run", "install-hooks"], cwd=ROOT, text=True)
        self.assertRegex(plan, "pre-commit install .*--hook-type pre-push")


if __name__ == "__main__":
    unittest.main()
