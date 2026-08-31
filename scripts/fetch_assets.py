#!/usr/bin/env python3
"""Download the landing page images once and commit them.

The design originally hot-linked picsum.photos. That service went down on
31 August 2026 and every image on the home page broke - our internet was fine,
the third party was not. The images are now downloaded once, committed to
shared/assets/, and served from our own nginx, so the running application has no
external image dependency at all.

This script records where the images came from and re-fetches them if they are
ever replaced. It is NOT run at build or deploy time.

    python3 scripts/fetch_assets.py

Source: Unsplash (https://unsplash.com), used under the Unsplash License, which
permits free use without permission. Provenance is recorded in
shared/assets/ATTRIBUTION.md.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "shared" / "assets"
BASE = "https://images.unsplash.com/"

# Each feature gets an image that matches what it does, so the card reads as the
# feature rather than as decoration.
IMAGES = [
    ("feature-01", "photo-1476514525535-07fb3b4ae5f1", 640, 780,
     "Trips & Itinerary - a boat looking out over an alpine lake"),
    ("feature-02", "photo-1414235077428-338989a2e8c0", 640, 780,
     "Attractions & Dining - a restaurant table"),
    ("feature-03", "photo-1522202176988-66273c2fd55f", 640, 780,
     "Travel Mate - two people planning together"),
    ("feature-04", "photo-1488646953014-85cb44e25828", 640, 780,
     "Account & Dashboard - a map, notebook and camera"),
    ("feature-05", "photo-1436491865332-7a61a109cc05", 640, 780,
     "Bookings & Budget - an aircraft wing above cloud"),
    ("hero", "photo-1506905925346-21bda4d32df4", 1800, 1400,
     "Hero background - mountains above cloud at sunset"),
]


def fetch(photo_id, width, height):
    """Fetch through curl rather than urllib.

    The python.org build on at least one team machine ships without a CA bundle,
    so urllib fails TLS verification on every HTTPS request while curl, which
    uses the system trust store, succeeds.
    """
    if shutil.which("curl") is None:
        raise RuntimeError("curl is not installed")

    url = f"{BASE}{photo_id}?w={width}&h={height}&fit=crop&q=80"
    result = subprocess.run(
        ["curl", "-sSL", "--fail", "--max-time", "30",
         "-A", "NextStop/1.0", url],
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode().strip() or f"curl exit {result.returncode}")
    return result.stdout


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    failures = []

    for name, photo_id, width, height, description in IMAGES:
        target = ASSETS / f"{name}.jpg"
        try:
            data = fetch(photo_id, width, height)
        except Exception as exc:
            # Never overwrite a committed image with a failure. The existing file
            # keeps working, which is the whole point of vendoring them.
            failures.append(f"{name}: {exc}")
            print(f"  {name:<12} FAILED ({exc}) - keeping the committed file")
            continue

        if not data.startswith(b"\xff\xd8"):
            failures.append(f"{name}: response was not a JPEG")
            print(f"  {name:<12} FAILED (not a JPEG) - keeping the committed file")
            continue

        target.write_bytes(data)
        print(f"  {name:<12} {len(data) // 1024:>4} KB  {description}")

    if failures:
        print(f"\n{len(failures)} image(s) could not be refreshed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
