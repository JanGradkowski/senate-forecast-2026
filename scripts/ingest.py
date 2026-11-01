"""Download all raw sources. Usage: python -m scripts.ingest [--force]"""

import argparse

from senate_forecast.data.download import fetch_all

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download everything")
    args = ap.parse_args()
    for rel, path in fetch_all(force=args.force).items():
        print(f"{rel:32s} {path.stat().st_size / 1e6:7.2f} MB")
