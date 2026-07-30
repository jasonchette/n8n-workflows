"""Pull current-season MLB stats via pybaseball and rank all players by CBS
league fantasy points.

Usage:
    python pull_fantasy_points.py --season 2026
"""

import argparse
import os

from pybaseball import batting_stats, pitching_stats

from scoring import add_batting_points, add_pitching_points


def main():
    parser = argparse.ArgumentParser(description="Compute CBS league fantasy points")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--qual", default=0, help="Minimum PA/IP to include (0 = every player)")
    parser.add_argument("--out-dir", default="output")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"Pulling {args.season} batting stats...")
    bat = batting_stats(args.season, qual=args.qual)
    bat = add_batting_points(bat)
    bat = bat.sort_values("FantasyPoints", ascending=False)
    bat_path = os.path.join(args.out_dir, f"batting_fantasy_points_{args.season}.csv")
    bat.to_csv(bat_path, index=False)
    print(f"Wrote {bat_path} ({len(bat)} players)")

    print(f"Pulling {args.season} pitching stats...")
    pit = pitching_stats(args.season, qual=args.qual)
    pit = add_pitching_points(pit)
    pit = pit.sort_values("FantasyPoints", ascending=False)
    pit_path = os.path.join(args.out_dir, f"pitching_fantasy_points_{args.season}.csv")
    pit.to_csv(pit_path, index=False)
    print(f"Wrote {pit_path} ({len(pit)} players)")


if __name__ == "__main__":
    main()
