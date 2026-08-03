"""Overrated / underrated finder: preseason ADP vs actual fantasy production.

Pulls consensus ADP from FantasyPros, computes every player's actual fantasy
points (MLB Stats API + league scoring rules), ranks both, and reports the
gap. Positive RankDelta = producing better than draft cost (underrated);
negative = drafted high but under-delivering (overrated).

Usage:
    python overrated_underrated.py --season 2026
"""

import argparse
import io
import os
import re
import unicodedata

import pandas as pd
import requests

from pull_fantasy_points import build_batting, build_pitching

ADP_URL = "https://www.fantasypros.com/mlb/adp/overall.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Trailing status tags FantasyPros appends after the (TEAM - POS) parens
NOTE_RE = re.compile(r"\s+(IL\d+|MiLB|DTD|NA|OUT|SUS)$")
PLAYER_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<team>[A-Z]{2,4}) - (?P<pos>[^)]+)\)")


def norm_name(name: str) -> str:
    """Accent/case/punctuation-insensitive key for joining data sources."""
    decomposed = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", stripped.replace(".", "")).strip().lower()


SUFFIX_RE = re.compile(r"\s+(jr|sr|ii|iii|iv|v)$")


def strip_suffix(key: str) -> str:
    return SUFFIX_RE.sub("", key)


def fetch_adp() -> pd.DataFrame:
    resp = requests.get(ADP_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    raw = pd.read_html(io.StringIO(resp.text), attrs={"id": "data"})[0]

    rows = []
    for _, r in raw.iterrows():
        label = str(r["Player (Team)"])
        note_m = NOTE_RE.search(label)
        note = note_m.group(1) if note_m else ""
        label = NOTE_RE.sub("", label)
        # Yahoo lists Ohtani separately as "(Batter)"/"(Pitcher)" — fold into one
        label = label.replace(" (Batter)", "").replace(" (Pitcher)", "")
        m = PLAYER_RE.match(label)
        if not m:
            continue
        rows.append({
            "Name": m.group("name"),
            "ADP_Team": m.group("team"),
            "Positions": m.group("pos"),
            "Status": note,
            "CBS_ADP": r["CBS"],
            "Consensus_ADP": r["AVG"],
        })
    df = pd.DataFrame(rows)
    # Duplicate names after folding (Batter)/(Pitcher): keep the best consensus ADP
    df = df.sort_values("Consensus_ADP").drop_duplicates("Name", keep="first")
    df["ADP_Rank"] = df["Consensus_ADP"].rank(method="min").astype(int)
    return df


def build_fp_table(season: int) -> pd.DataFrame:
    bat = build_batting(season)[["Name", "PA", "FantasyPoints"]]
    pit = build_pitching(season)[["Name", "IP", "FantasyPoints"]]
    both = pd.concat([bat, pit], ignore_index=True)
    # Two-way players appear in both tables; total value is the sum
    fp = both.groupby("Name", as_index=False).agg(
        PA=("PA", "max"), IP=("IP", "max"), FantasyPoints=("FantasyPoints", "sum")
    )
    fp["FP_Rank"] = fp["FantasyPoints"].rank(ascending=False, method="min").astype(int)
    return fp


def main():
    parser = argparse.ArgumentParser(description="ADP vs production rank deltas")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--out-dir", default="output")
    parser.add_argument("--top", type=int, default=15, help="How many names to print per list")
    parser.add_argument("--min-pa", type=int, default=100,
                        help="Playing-time floor for the printed lists: batters need this many PA")
    parser.add_argument("--min-ip", type=int, default=30,
                        help="Playing-time floor for the printed lists: pitchers need this many IP")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print("Pulling consensus ADP from FantasyPros...")
    adp = fetch_adp()
    print(f"  {len(adp)} drafted players")

    print(f"Computing {args.season} fantasy points from the MLB Stats API...")
    fp = build_fp_table(args.season)

    adp["_key"] = adp["Name"].map(norm_name)
    fp["_key"] = fp["Name"].map(norm_name)
    fp_dedup = fp.sort_values("FantasyPoints", ascending=False).drop_duplicates("_key")

    fp_cols = fp_dedup[["_key", "PA", "IP", "FantasyPoints", "FP_Rank"]]
    merged = adp.merge(fp_cols, on="_key", how="left")

    # Fallback for suffix mismatches between sources ("Cedric Mullins II" vs
    # "Cedric Mullins"): retry unmatched rows with suffixes stripped, but only
    # accept keys that are unambiguous on both sides.
    miss = merged["FantasyPoints"].isna()
    if miss.any():
        fp_fb = fp_cols.assign(_fb=fp_cols["_key"].map(strip_suffix))
        fp_fb = fp_fb[~fp_fb["_fb"].duplicated(keep=False)].drop(columns="_key")
        fallback = (
            merged.loc[miss, ["_key"]]
            .assign(_fb=lambda d: d["_key"].map(strip_suffix))
            .merge(fp_fb, on="_fb", how="left")
        )
        for col in ("PA", "IP", "FantasyPoints", "FP_Rank"):
            merged.loc[miss, col] = fallback[col].values
    merged = merged.drop(columns="_key")

    unmatched = merged["FantasyPoints"].isna().sum()
    if unmatched:
        print(f"  Note: {unmatched} ADP players have no {args.season} MLB stats "
              f"(injured all year, in the minors, or name mismatch) — excluded from deltas.")

    merged["RankDelta"] = merged["ADP_Rank"] - merged["FP_Rank"]
    merged = merged.sort_values("RankDelta", ascending=False)

    out_path = os.path.join(args.out_dir, f"adp_value_deltas_{args.season}.csv")
    merged.to_csv(out_path, index=False)
    print(f"Wrote {out_path} ({len(merged)} players)")

    rated = merged.dropna(subset=["RankDelta"]).copy()
    rated[["RankDelta", "FP_Rank"]] = rated[["RankDelta", "FP_Rank"]].astype(int)
    # Playing-time floor keeps season-long injuries and call-ups out of the
    # printed lists; the full unfiltered table is in the CSV.
    playing = rated[(rated["PA"] >= args.min_pa) | (rated["IP"] >= args.min_ip)]
    skipped = len(rated) - len(playing)
    cols = ["Name", "Positions", "Status", "ADP_Rank", "FP_Rank", "FantasyPoints", "RankDelta"]

    print(f"\n=== TOP {args.top} UNDERRATED (outproducing draft cost) ===")
    print(playing.head(args.top)[cols].to_string(index=False))
    print(f"\n=== TOP {args.top} OVERRATED (drafted high, under-delivering) ===")
    print(playing.tail(args.top)[cols].iloc[::-1].to_string(index=False))
    if skipped:
        print(f"\n({skipped} players below the playing-time floor of {args.min_pa} PA / "
              f"{args.min_ip} IP — mostly injured or demoted — are in the CSV but not shown.)")


if __name__ == "__main__":
    main()
