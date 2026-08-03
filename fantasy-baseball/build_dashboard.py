"""Generate the self-contained HTML dashboard from live data.

Pulls fresh season stats and ADP, embeds the data as JSON into
dashboard_template.html, and writes:

  output/dashboard.html          — standalone file, open directly in a browser
  output/dashboard_artifact.html — body-only variant for claude.ai artifact publishing

Usage:
    python build_dashboard.py --season 2026
"""

import argparse
import datetime
import json
import os

import pandas as pd
import requests

from overrated_underrated import build_delta_table
from pull_fantasy_points import HEADERS, build_batting, build_pitching

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")

BAT_STATS = ["1B", "2B", "3B", "HR", "BB", "HBP", "R", "RBI", "SB", "CS", "SO"]
PIT_STATS = ["IP", "SO", "SV", "HLD", "BB", "HBP", "ER", "H"]


def team_abbrevs() -> dict:
    resp = requests.get(
        "https://statsapi.mlb.com/api/v1/teams",
        params={"sportId": 1}, headers=HEADERS, timeout=30,
    )
    resp.raise_for_status()
    return {t["name"]: t.get("abbreviation", t["name"]) for t in resp.json()["teams"]}


def _num(v, ndigits=None):
    """NaN-safe number for JSON; None if missing."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    v = float(v)
    if ndigits is not None:
        v = round(v, ndigits)
    return int(v) if v == int(v) else v


def batting_rows(df: pd.DataFrame, abbr: dict) -> list:
    df = df.sort_values("FantasyPoints", ascending=False)
    return [
        {
            "n": r["Name"],
            "t": abbr.get(r["Team"], r["Team"]),
            "PA": _num(r["PA"]),
            "s": {k: _num(r[k]) for k in BAT_STATS},
            "fp": _num(r["FantasyPoints"], 1),
        }
        for _, r in df.iterrows()
    ]


def pitching_rows(df: pd.DataFrame, abbr: dict) -> list:
    df = df.sort_values("FantasyPoints", ascending=False)
    return [
        {
            "n": r["Name"],
            "t": abbr.get(r["Team"], r["Team"]),
            "IP": _num(r["IP"], 2),
            "s": {k: _num(r[k], 2 if k == "IP" else None) for k in PIT_STATS},
            "fp": _num(r["FantasyPoints"], 1),
        }
        for _, r in df.iterrows()
    ]


def adp_rows(df: pd.DataFrame) -> list:
    return [
        {
            "n": r["Name"],
            "pos": r["Positions"],
            "st": r["Status"] or "",
            "cbs": _num(r["CBS_ADP"]),
            "avg": _num(r["Consensus_ADP"], 1),
            "ar": _num(r["ADP_Rank"]),
            "fr": _num(r["FP_Rank"]),
            "pa": _num(r["PA"]) or 0,
            "ip": _num(r["IP"], 1) or 0,
            "fp": _num(r["FantasyPoints"], 1),
            "d": _num(r["RankDelta"]),
        }
        for _, r in df.iterrows()
    ]


def main():
    parser = argparse.ArgumentParser(description="Build the dashboard HTML")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--out-dir", default="output")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    abbr = team_abbrevs()
    today = datetime.date.today()

    periods = []
    for pid, label, days in [
        ("season", "Full season", None),
        ("d30", "Last 30 days", 30),
        ("d14", "Last 14 days", 14),
        ("d7", "Last 7 days", 7),
    ]:
        start = (today - datetime.timedelta(days=days)).isoformat() if days else None
        end = today.isoformat() if days else None
        print(f"Pulling {args.season} stats — {label.lower()}...")
        periods.append({
            "id": pid,
            "label": label,
            "bat": batting_rows(build_batting(args.season, start, end), abbr),
            "pit": pitching_rows(build_pitching(args.season, start, end), abbr),
        })

    delta = adp_rows(build_delta_table(args.season))

    data = {
        "season": args.season,
        "generated": today.isoformat(),
        "periods": periods,
        "adp": delta,
    }
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    with open(TEMPLATE, encoding="utf-8") as f:
        body = f.read().replace("__DATA_JSON__", payload)

    artifact_path = os.path.join(args.out_dir, "dashboard_artifact.html")
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write(body)

    standalone_path = os.path.join(args.out_dir, "dashboard.html")
    with open(standalone_path, "w", encoding="utf-8") as f:
        f.write(
            '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            "</head>\n<body>\n" + body + "\n</body>\n</html>\n"
        )

    for path in (standalone_path, artifact_path):
        print(f"Wrote {path} ({os.path.getsize(path) // 1024} KB)")


if __name__ == "__main__":
    main()
