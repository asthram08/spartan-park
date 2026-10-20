"""Spartan Park data collector.

Reads how full each SJSU parking garage is from the public status page
and adds one row per garage to data/garage_fullness.csv.

Run it by hand:   python collector.py
GitHub Actions runs it every 10 minutes (see .github/workflows/collect.yml).
"""

import csv
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

URL = "https://sjsuparkingstatus.sjsu.edu/"
CSV_PATH = os.path.join("data", "garage_fullness.csv")
HEADER = ["collected_at_utc", "page_updated", "garage", "fullness_pct", "raw_text"]


def fetch_page(url=URL):
    request = urllib.request.Request(
        url, headers={"User-Agent": "spartan-park student project (data collector)"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        # SJSU's server sends an incomplete certificate chain. Browsers fill in the
        # missing piece; Python does not. This page is public and read-only and we
        # send nothing private, so we retry without the certificate check.
        if "CERTIFICATE_VERIFY_FAILED" not in str(error):
            raise
        print("Note: SJSU certificate incomplete; retrying without verification.")
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, timeout=30, context=context) as response:
            return response.read().decode("utf-8", errors="replace")


def parse(html):
    """Return (page_updated, [(garage, fullness_pct or None, raw_text), ...])."""
    updated = re.search(r"Last updated\s*([^<]+)", html)
    page_updated = updated.group(1).strip() if updated else ""

    names = re.findall(r'class="garage__name">\s*([^<]+?)\s*<', html)
    values = re.findall(r'class="garage__fullness">\s*([^<]*?)\s*<', html)
    if not names or len(names) != len(values):
        raise ValueError(f"Page layout changed: found {len(names)} names, {len(values)} values")

    rows = []
    for name, raw in zip(names, values):
        number = re.search(r"\d+", raw)
        if number:
            pct = int(number.group())
        elif "full" in raw.lower():
            pct = 100
        else:
            pct = None
        rows.append((name, pct, raw))
    return page_updated, rows


def save(page_updated, rows, path=CSV_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_file = not os.path.exists(path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(HEADER)
        for garage, pct, raw in rows:
            writer.writerow([now, page_updated, garage, "" if pct is None else pct, raw])


def main():
    try:
        html = fetch_page()
        page_updated, rows = parse(html)
    except Exception as error:  # stop with an error so the failed run shows up in GitHub
        print(f"Collector failed: {error}", file=sys.stderr)
        sys.exit(1)
    save(page_updated, rows)
    for garage, pct, _ in rows:
        print(f"{garage}: {pct}%")


if __name__ == "__main__":
    main()
