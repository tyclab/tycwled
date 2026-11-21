"""Refuse private lamp data in the staged index or in the commits about to be published.

Without arguments it reads the staged index (pre-commit) or, when pre-commit's pre-push stage
names a ref, the commits of that ref no remote has yet. With rev-list arguments (CI) it reads
exactly those commits. A range is also refused when it holds history from before the purge.
"""
import bz2
import gzip
import io
import json
import lzma
import os
import re
import subprocess
import sys
import tarfile
import zipfile


# First commit of the rewritten history. Every later commit must descend from it.
REWRITTEN_FROM = "88431022f4de464f06a5ee22a75d6c96665d23f3"
FACTORY_CONFIG = "glorb/factory-0.14.4-GLORB.1.3/cfg.json"
COLLECTOR_CONFIG = "fleet/platformio_override.ini"
PRIVATE_PATH = re.compile(r"(^|/)(captures/|pre-flash-backup/|(struct|verify)-p[0-9]+\.json(\.gz)?\Z|cfg\.json\Z)")

# Values that identify nobody: RFC 7042 documentation MACs, the null and broadcast MAC,
# names that start with "example", WLED's own access point name, an unset coordinate.
PUBLIC_MAC = re.compile(rb"(?i)(00[:-]?00[:-]?5e[:-]?00[:-]?53[:-]?[0-9a-f]{2}|(00[:-]?){5}00|(ff[:-]?){5}ff)\Z")
PUBLIC_NAME = re.compile(rb"(?i)(example.*|WLED-AP)?\Z")
MAC = re.compile(rb"(?<![0-9A-Fa-f:.-])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:-])")
QUOTE = rb"\\*[\"']"
MAC_FIELD = re.compile(rb"(?i)" + QUOTE + rb"(?:mac|bssid)" + QUOTE + rb"\s*:\s*" + QUOTE + rb"([0-9a-f]{12})" + QUOTE)
NAME_FIELD = re.compile(rb"(?i)" + QUOTE + rb"b?ssid" + QUOTE + rb"\s*:\s*" + QUOTE + rb"([^\"'\\]*)" + QUOTE)
COORDINATE = re.compile(QUOTE + rb"l[tn]" + QUOTE + rb"\s*:\s*(-?[0-9]+(?:\.[0-9]+)?)")
PRIVATE_V4 = re.compile(rb"(?<![0-9.])(?:10(?:\.[0-9]{1,3}){3}|192\.168(?:\.[0-9]{1,3}){2}"
                        rb"|172\.(?:1[6-9]|2[0-9]|3[01])(?:\.[0-9]{1,3}){2})(?![0-9.])")
PRIVATE_V6 = re.compile(rb"(?i)(?<![0-9a-f:])f[cd][0-9a-f]{2}:[0-9a-f]{0,4}:[0-9a-f:]+")
COLLECTOR = re.compile(rb"SYSLOG_EVENTS_HOST=\\?\"[0-9.]+\\?\"")
UNREADABLE = {b"\x28\xb5\x2f\xfd": "zstd", b"7z\xbc\xaf\x27\x1c": "7z", b"Rar!\x1a\x07": "rar"}


def git(*args, stdin=None):
    return subprocess.run(["git", *args], input=stdin, capture_output=True, check=True).stdout


def layers(data, depth=0):
    """The bytes as stored and every layer a compressed or archived file unpacks to."""
    yield data
    inner = []
    try:
        if data[:2] == b"\x1f\x8b":
            inner = [gzip.decompress(data)]
        elif data[:3] == b"BZh" and data[4:10] == b"1AY&SY":
            inner = [bz2.decompress(data)]
        elif data[:6] == b"\xfd7zXZ\x00":
            inner = [lzma.decompress(data)]
        elif data[:4] == b"PK\x03\x04":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                inner = [archive.read(name) for name in archive.namelist()]
        elif data[257:262] == b"ustar":
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                inner = [archive.extractfile(member).read() for member in archive if member.isfile()]
        elif any(data.startswith(magic) for magic in UNREADABLE):
            raise ValueError
    except Exception:
        raise ValueError("compressed data this check cannot read") from None
    if inner and depth == 4:
        raise ValueError("compressed data nested too deep to read")
    for part in inner:
        yield from layers(part, depth + 1)


def recording(text):
    """wledlab's capture formats: a series of [time, cells] frames, bare or under frames, ref or tgt."""
    if text[:64].lstrip()[:1] not in (b"{", b"["):
        return False
    try:
        doc = json.loads(text)
    except ValueError:
        return False
    series = [doc] if isinstance(doc, list) else [doc.get(key) for key in ("frames", "ref", "tgt")] if isinstance(doc, dict) else []
    return any(isinstance(frames, list) and frames and all(
        isinstance(frame, list) and len(frame) == 2 and isinstance(frame[0], (int, float)) and isinstance(frame[1], list)
        for frame in frames[:8]) for frames in series)


def findings(path, data):
    """Why this file must stay private, without quoting the value."""
    found = set()
    if path != FACTORY_CONFIG and PRIVATE_PATH.search(path):
        found.add("a raw capture or device backup")
    try:
        for text in layers(data):
            if path == COLLECTOR_CONFIG:
                text = COLLECTOR.sub(b"", text)
            if recording(text):
                found.add("a raw lamp recording")
            if any(not PUBLIC_MAC.match(mac) for mac in MAC.findall(text) + MAC_FIELD.findall(text)):
                found.add("a MAC address")
            if PRIVATE_V4.search(text) or PRIVATE_V6.search(text):
                found.add("a private network address")
            if any(not PUBLIC_NAME.match(name) for name in NAME_FIELD.findall(text)):
                found.add("a Wi-Fi network name or BSSID")
            if any(float(value) for value in COORDINATE.findall(text)):
                found.add("a location")
    except ValueError as unreadable:
        found.add(str(unreadable))
    return sorted(found)


def blobs(listing):
    """Content of every listed (object id, path) pair that is a file."""
    listing = sorted(set(listing))
    out = io.BytesIO(git("cat-file", "--batch", stdin="".join(f"{oid}\n" for oid, _ in listing).encode()))
    for _, path in listing:
        header = out.readline().split()
        if header[1] == b"missing":
            continue
        data = out.read(int(header[2]) + 1)[:-1]
        if header[1] == b"blob":
            yield path, data


def staged():
    entries = git("ls-files", "--stage", "-z").decode("utf-8", "surrogateescape").split("\0")
    return [(entry.split()[1], entry.split("\t", 1)[1]) for entry in entries if entry and not entry.startswith("160000")]


def published(revs):
    lines = git("rev-list", "--objects", *revs).decode("utf-8", "surrogateescape").splitlines()
    return [tuple(line.split(" ", 1)) for line in lines if " " in line and line.split(" ", 1)[1]]


def off_lineage(revs, start=REWRITTEN_FROM):
    """Commits behind the published tips that do not descend from the rewritten history's first commit;
    None when this clone does not hold that commit."""
    if subprocess.run(["git", "cat-file", "-e", f"{start}^{{commit}}"], capture_output=True).returncode:
        return None
    tips = [rev for rev in git("rev-parse", "--revs-only", *revs).decode().split() if not rev.startswith("^")]
    later = set(git("rev-list", *tips, "--not", start).decode().split())
    return sorted(later - set(git("rev-list", "--ancestry-path", *tips, "--not", start).decode().split()))


def problems(revs=None, start=REWRITTEN_FROM):
    out = []
    if revs:
        strays = off_lineage(revs, start)
        if strays is None:
            out.append("The rewritten history is not in this clone. Fetch origin/main in full, then publish.")
        elif strays:
            out.append(f"{len(strays)} commit(s) come from the history before the recordings were removed "
                       f"(first: {strays[0][:12]}). Start the branch again from origin/main.")
    for path, data in blobs(published(revs) if revs else staged()):
        out += [f"{path}: {reason}" for reason in findings(path, data)]
    return out


def main():
    revs = sys.argv[1:]
    # pre-commit's pre-push stage: a first push of a whole history names only the local branch.
    ref = os.environ.get("PRE_COMMIT_TO_REF") or os.environ.get("PRE_COMMIT_LOCAL_BRANCH")
    if not revs and ref:
        revs = [ref, "--not", "--remotes"]
    found = problems(revs)
    if found:
        print("\n".join(found), file=sys.stderr)
        sys.exit("Publish the verify summary and keep raw captures, device backups and network details in private "
                 "storage. Tests and examples use documentation values (CONTRIBUTING.md).")


if __name__ == "__main__":
    main()
