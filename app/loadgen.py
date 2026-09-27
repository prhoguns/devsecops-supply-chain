"""Traffic generator for demo-api.

Runs from the same signed image as the API (`python -m app.loadgen`), so the cluster never has to
admit an unsigned or third-party image just to create load. Standard library only.
"""

import os
import time
import urllib.error
import urllib.request


def hit(url: str, timeout: float = 2.0) -> int:
    """Request url once and return the HTTP status, or 0 if the request failed at the network level.

    Network errors (refused, reset, timed out) must never crash the generator: they happen
    during every rolling update of the API, which is exactly when the traffic matters most.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as err:
        return err.code
    except OSError:  # URLError, ConnectionResetError, TimeoutError, ...
        return 0


def main() -> None:
    url = os.getenv("TARGET_URL", "http://demo-api/api/work")
    interval = float(os.getenv("INTERVAL_SECONDS", "0.2"))
    report_every = float(os.getenv("REPORT_SECONDS", "30"))
    counts: dict[int, int] = {}
    last_report = time.monotonic()
    while True:
        status = hit(url)
        counts[status] = counts.get(status, 0) + 1
        if time.monotonic() - last_report >= report_every:
            print(f"loadgen {url} status counts: {dict(sorted(counts.items()))}", flush=True)
            counts.clear()
            last_report = time.monotonic()
        time.sleep(interval)


if __name__ == "__main__":
    main()
