#!/usr/bin/env python3
"""Block until the given services answer /health, or fail the build.

    python3 scripts/wait_for_health.py 5201 5101
"""

import sys
import time
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 120
INTERVAL_SECONDS = 2


def is_healthy(port):
    try:
        with urllib.request.urlopen(
            f"http://localhost:{port}/health", timeout=3
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main():
    ports = [int(arg) for arg in sys.argv[1:]]
    if not ports:
        print("usage: wait_for_health.py PORT [PORT ...]", file=sys.stderr)
        return 2

    deadline = time.monotonic() + TIMEOUT_SECONDS
    pending = list(ports)

    while pending and time.monotonic() < deadline:
        pending = [port for port in pending if not is_healthy(port)]
        if pending:
            time.sleep(INTERVAL_SECONDS)

    if pending:
        print(f"FAIL: no /health response on {pending} after {TIMEOUT_SECONDS}s")
        return 1

    print(f"All services healthy: {ports}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
