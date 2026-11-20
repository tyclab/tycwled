"""Private lamp files may remain on disk after removing them from the public tree."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECK = Path(__file__).resolve().parents[1] / "tools" / "check_private_lamp_data.py"


class PrivateLampData(unittest.TestCase):
    def test_removed_file_and_pushed_ref(self):
        with tempfile.TemporaryDirectory() as directory:
            env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PRE_COMMIT"))}

            def git(*args):
                return subprocess.check_output(["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                                                "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false",
                                                *args], cwd=directory, env=env).strip().decode()

            def check(**refs):
                return subprocess.run([sys.executable, CHECK], cwd=directory, env={**env, **refs},
                                      capture_output=True).returncode

            git("init", "--quiet")
            root = Path(directory)
            (root / ".gitignore").write_text("captures/\n")
            capture = root / "captures" / "verify-p1.json.gz"
            capture.parent.mkdir()
            capture.write_bytes(b"fixture")
            git("add", ".gitignore")
            git("add", "--force", "captures")
            self.assertEqual(check(), 1)
            git("commit", "--quiet", "-m", "fixture")
            raw = git("rev-parse", "HEAD")
            git("rm", "--cached", "--quiet", str(capture))
            self.assertTrue(capture.exists())
            self.assertEqual(check(), 0)
            self.assertEqual(check(PRE_COMMIT_TO_REF=raw), 1)
            git("commit", "--quiet", "-m", "remove fixture")
            clean = git("rev-parse", "HEAD")
            git("add", "--force", "captures")
            self.assertEqual(check(), 1)
            self.assertEqual(check(PRE_COMMIT_TO_REF=clean), 0)
            self.assertEqual(check(PRE_COMMIT_LOCAL_BRANCH=clean), 0)
