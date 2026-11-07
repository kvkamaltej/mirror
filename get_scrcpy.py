"""Download the official scrcpy Windows release into ./bin (needed only to BUILD Mirror).

    python get_scrcpy.py                 # scrcpy 2.5 into ./bin
    python get_scrcpy.py --dest DIR      # somewhere else
    python get_scrcpy.py --version 2.5

Standard library only. The archive is checked against the SHA-256 digest GitHub
publishes for the release asset; if the digests don't match, nothing is written.
scrcpy is Apache-2.0: https://github.com/Genymobile/scrcpy
"""
import argparse
import fnmatch
import hashlib
import io
import json
import os
import sys
import urllib.request
import zipfile

REPO = "Genymobile/scrcpy"
DEFAULT_VERSION = "2.5"  # the version Mirror is tested with (its remote bar uses scrcpy's shortcuts)
KEEP = ["scrcpy.exe", "scrcpy-server", "icon.png", "adb.exe", "AdbWinApi.dll", "AdbWinUsbApi.dll",
        "SDL2.dll", "SDL3.dll", "avcodec-*.dll", "avformat-*.dll", "avutil-*.dll", "swresample-*.dll",
        "libusb-1.0.dll"]


def http_get(url, accept=None):
    req = urllib.request.Request(url, headers={"User-Agent": "mirror-get-scrcpy"})
    if accept:
        req.add_header("Accept", accept)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def release_asset(version, name):
    """(download URL, expected sha256, where it came from) for one asset of a scrcpy release.

    The digest GitHub publishes for the asset is used when there is one; older
    releases (like 2.5) instead ship a SHA256SUMS.txt file next to the archives."""
    rel = json.loads(http_get("https://api.github.com/repos/%s/releases/tags/v%s" % (REPO, version),
                              "application/vnd.github+json"))
    assets = {a["name"]: a for a in rel.get("assets", [])}
    if name not in assets:
        raise SystemExit("scrcpy v%s has no asset %s" % (version, name))
    a = assets[name]
    digest = a.get("digest") or ""
    if digest.startswith("sha256:"):
        return a["browser_download_url"], digest.split(":", 1)[1], "GitHub asset digest"
    if "SHA256SUMS.txt" in assets:
        sums = http_get(assets["SHA256SUMS.txt"]["browser_download_url"]).decode("utf-8", "replace")
        for line in sums.splitlines():
            f = line.split()
            if len(f) >= 2 and f[-1].lstrip("*") == name:
                return a["browser_download_url"], f[0], "the release's SHA256SUMS.txt"
    return a["browser_download_url"], None, None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--dest", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin"))
    args = ap.parse_args()

    name = "scrcpy-win64-v%s.zip" % args.version
    url, want, source = release_asset(args.version, name)
    print("Downloading %s" % url)
    data = http_get(url)
    got = hashlib.sha256(data).hexdigest()
    if not want:
        raise SystemExit("No published SHA-256 for %s (sha256 of the download: %s); refusing to install it "
                         "unchecked." % (name, got))
    if got != want.lower():
        raise SystemExit("Checksum mismatch for %s:\n  expected %s\n  got      %s\nNothing was written."
                         % (name, want, got))
    print("  %.1f MB, sha256 verified against %s" % (len(data) / 1e6, source))

    os.makedirs(args.dest, exist_ok=True)
    written = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            base = os.path.basename(info.filename)
            if not base or info.is_dir() or not any(fnmatch.fnmatch(base, k) for k in KEEP):
                continue
            with z.open(info) as src, open(os.path.join(args.dest, base), "wb") as dst:
                dst.write(src.read())
            written.append(base)
    if "scrcpy.exe" not in written or "adb.exe" not in written:
        raise SystemExit("The archive did not contain scrcpy.exe and adb.exe")
    print("scrcpy %s: %d files in %s" % (args.version, len(written), args.dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
