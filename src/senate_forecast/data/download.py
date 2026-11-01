"""Download every raw source into data/raw/<source>/. Downloads are data, never code."""

import tarfile
import time
import zipfile
from pathlib import Path

import httpx

from senate_forecast.paths import RAW

DATAVERSE = "https://dataverse.harvard.edu/api/access/datafile/{}?format=original"
GH_RAW = "https://raw.githubusercontent.com"
WAYBACK = "http://web.archive.org/web/{}id_/https://projects.fivethirtyeight.com/polls/data/{}"
HEADERS = {"User-Agent": "senate-forecast-2026/0.1 (student research project)"}

SOURCES = {
    # MIT Election Lab, Senate returns 1976-2024 (doi:10.7910/DVN/PEJ5QU)
    "medsl/senate.csv": DATAVERSE.format(13887039),
    # MIT Election Lab, presidential returns by state 1976-2024 (doi:10.7910/DVN/42MVDX)
    "medsl/president.csv": DATAVERSE.format(13887042),
    # 538 archive: polls from the final 21 days with actual results, 1998-2022
    "538/raw_polls.csv": f"{GH_RAW}/fivethirtyeight/data/master/pollster-ratings/raw_polls.csv",
    # 538's live poll files as archived just after the 2024 election (raw_polls ends in 2022)
    "538/senate_polls_2024.csv": WAYBACK.format("20241118073720", "senate_polls.csv"),
    "538/generic_ballot_polls_2024.csv": WAYBACK.format("20241127022426", "generic_ballot_polls.csv"),
    # electoral-vote.com 2026 Senate polls
    "evp/senate_polls.csv": "https://www.electoral-vote.com/evp2026/Senate/senate_polls.csv",
    # 2026 candidates and the expert-ratings table
    "wikipedia/2026_senate.html": "https://en.wikipedia.org/wiki/2026_United_States_Senate_elections",
    # PredictIt's public market data (reference prices and a typo check; not the trading venue)
    "predictit_live/all.json": "https://www.predictit.org/api/marketdata/all/",
    # Expert-ratings tables for the PredictIt years (same source and parser as 2026)
    **{f"wikipedia/{y}_senate.html": f"https://en.wikipedia.org/wiki/{y}_United_States_Senate_elections"
       for y in (2016, 2018, 2020)},
    # PredictIt daily prices (k5cents/predelect)
    "predelect/2016_markets.csv": f"{GH_RAW}/k5cents/predelect/master/2016/data/2016_markets.csv",
    "predelect/2016_daily.zip": f"{GH_RAW}/k5cents/predelect/master/2016/data/DailyMarketData.zip",
    "predelect/2018_markets.csv": f"{GH_RAW}/k5cents/predelect/master/2018/data/2018_markets.csv",
    "predelect/2018_daily.zip": f"{GH_RAW}/k5cents/predelect/master/2018/data/DailyMarketData.zip",
    "predelect/2020.tar.xz": f"{GH_RAW}/k5cents/predelect/master/2020/data/2020.tar.xz",
}

# Sources that change daily and should be re-fetched on every run.
LIVE = {"evp/senate_polls.csv", "wikipedia/2026_senate.html", "predictit_live/all.json"}


def fetch(rel: str, url: str, force: bool = False) -> Path:
    dest = RAW / rel
    if dest.exists() and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if "wikipedia.org" in url:
        time.sleep(5)  # Wikipedia rate-limits back-to-back requests with a 403
    with httpx.stream("GET", url, headers=HEADERS, follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        tmp = dest.with_suffix(dest.suffix + ".part")
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    tmp.replace(dest)
    return dest


def extract(archive: Path) -> Path:
    """Unpack an archive next to itself, refusing paths that escape the target folder."""
    target = archive.parent / archive.name.split(".")[0]
    if target.exists():
        return target
    target.mkdir()
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not (target / name).resolve().is_relative_to(target.resolve()):
                    raise ValueError(f"unsafe path in {archive}: {name}")
            z.extractall(target)
    else:
        with tarfile.open(archive) as t:
            t.extractall(target, filter="data")
    return target


def fetch_all(force: bool = False) -> dict[str, Path]:
    out = {}
    for rel, url in SOURCES.items():
        path = fetch(rel, url, force=force or rel in LIVE)
        if path.suffix in {".zip", ".xz"}:
            extract(path)
        out[rel] = path
    return out
