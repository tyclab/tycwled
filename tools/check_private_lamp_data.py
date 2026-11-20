"""Check the staged index or pushed tree for private lamp recordings and device backups."""
import os
import re
import subprocess
import sys


FACTORY_CONFIG = b"glorb/factory-0.14.4-GLORB.1.3/cfg.json"
PRIVATE_DATA = re.compile(rb"(^|/)(captures/|pre-flash-backup/|(struct|verify)-p[0-9]+\.json(\.gz)?\Z|cfg\.json\Z)")


def main():
    # A first push to an empty remote supplies the local ref without a commit range.
    ref = os.environ.get("PRE_COMMIT_TO_REF") or os.environ.get("PRE_COMMIT_LOCAL_BRANCH")
    cmd = ["git", "ls-tree", "-rz", "--name-only", ref, "--"] if ref else ["git", "ls-files", "--cached", "-z"]
    paths = subprocess.check_output(cmd).split(b"\0")
    if any(path != FACTORY_CONFIG and PRIVATE_DATA.search(path) for path in paths):
        sys.exit("Publish the verify summary and keep raw captures and device backups in private storage.")


if __name__ == "__main__":
    main()
