"""Pull current-season MLB stats from the official MLB Stats API and rank
all players by CBS league fantasy points.

Usage:
    python pull_fantasy_points.py --season 2026
"""

import argparse
import os

import pandas as pd
import requests

from scoring import add_batting_points, add_pitching_points

STATS_API = "https://statsapi.mlb.com/api/v1/stats"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _parse_innings(ip_str: str) -> float:
    """Converts baseball innings notation ('127.1' = 127 and 1/3 innings) to a true decimal."""
    whole, _, frac = str(ip_str).partition(".")
    thirds = {"0": 0.0, "1": 1 / 3, "2": 2 / 3}
    return int(whole) + thirds.get(frac, 0.0)


def fetch_stats(season: int, group: str) -> pd.DataFrame:
    params = {
        "stats": "season",
        "group": group,
        "season": season,
        "sportId": 1,
        "limit": 2000,
        "playerPool": "ALL",
    }
    resp = requests.get(STATS_API, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    splits = resp.json()["stats"][0]["splits"]

    rows = []
    for split in splits:
        row = {
            "Name": split["player"]["fullName"],
            "Team": split.get("team", {}).get("name", ""),
        }
        row.update(split["stat"])
        rows.append(row)
    return pd.DataFrame(rows)


def build_batting(season: int) -> pd.DataFrame:
    df = fetch_stats(season, "hitting")
    df = df.rename(columns={
        "hits": "H", "doubles": "2B", "triples": "3B", "homeRuns": "HR",
        "baseOnBalls": "BB", "hitByPitch": "HBP", "runs": "R", "rbi": "RBI",
        "stolenBases": "SB", "caughtStealing": "CS", "strikeOuts": "SO",
        "plateAppearances": "PA",
    })
    return add_batting_points(df)


def build_pitching(season: int) -> pd.DataFrame:
    df = fetch_stats(season, "pitching")
    df["IP"] = df["inningsPitched"].apply(_parse_innings)
    df = df.rename(columns={
        "strikeOuts": "SO", "saves": "SV", "holds": "HLD",
        "baseOnBalls": "BB", "hitBatsmen": "HBP", "earnedRuns": "ER", "hits": "H",
    })
    return add_pitching_points(df)


def main():
    parser = argparse.ArgumentParser(description="Compute CBS league fantasy points")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--out-dir", default="output")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"Pulling {args.season} batting stats from the MLB Stats API...")
    bat = build_batting(args.season)
    bat = bat.sort_values("FantasyPoints", ascending=False)
    bat_path = os.path.join(args.out_dir, f"batting_fantasy_points_{args.season}.csv")
    bat.to_csv(bat_path, index=False)
    print(f"Wrote {bat_path} ({len(bat)} players)")

    print(f"Pulling {args.season} pitching stats from the MLB Stats API...")
    pit = build_pitching(args.season)
    pit = pit.sort_values("FantasyPoints", ascending=False)
    pit_path = os.path.join(args.out_dir, f"pitching_fantasy_points_{args.season}.csv")
    pit.to_csv(pit_path, index=False)
    print(f"Wrote {pit_path} ({len(pit)} players)")


if __name__ == "__main__":
    main()
