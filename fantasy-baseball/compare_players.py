"""Head-to-head comparison of two players under the CBS league scoring rules.

Looks up both players by name on the official MLB Stats API, pulls their
season stats, and prints a side-by-side per-category points breakdown.

Usage:
    python compare_players.py "Yordan Alvarez" "James Wood" --season 2026
"""

import argparse
import sys
import unicodedata

import requests

from scoring import BATTING_WEIGHTS, PITCHING_WEIGHTS, breakdown

API_BASE = "https://statsapi.mlb.com/api/v1"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# API field name -> the stat code used in the weight tables
BATTING_MAP = {
    "doubles": "2B", "triples": "3B", "homeRuns": "HR", "baseOnBalls": "BB",
    "hitByPitch": "HBP", "runs": "R", "rbi": "RBI", "stolenBases": "SB",
    "caughtStealing": "CS", "strikeOuts": "SO",
}
PITCHING_MAP = {
    "strikeOuts": "SO", "saves": "SV", "holds": "HLD", "baseOnBalls": "BB",
    "hitBatsmen": "HBP", "earnedRuns": "ER", "hits": "H",
}

STAT_LABELS = {
    "1B": "Singles", "2B": "Doubles", "3B": "Triples", "HR": "Home Runs",
    "BB": "Walks", "HBP": "Hit by Pitch", "R": "Runs", "RBI": "RBI",
    "SB": "Stolen Bases", "CS": "Caught Stealing", "SO": "Strikeouts",
    "IP": "Innings Pitched", "QS": "Quality Starts", "SV": "Saves",
    "HLD": "Holds", "ER": "Earned Runs", "H": "Hits Allowed",
}


def _parse_innings(ip_str) -> float:
    whole, _, frac = str(ip_str).partition(".")
    thirds = {"0": 0.0, "1": 1 / 3, "2": 2 / 3}
    return int(whole) + thirds.get(frac, 0.0)


def _norm(name: str) -> str:
    """Accent-insensitive, case-insensitive name form ('García' == 'garcia')."""
    decomposed = unicodedata.normalize("NFD", name)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _describe(p: dict) -> str:
    pos = p.get("primaryPosition", {}).get("abbreviation", "?")
    team = p.get("currentTeam", {}).get("name", "no team")
    return f"{p['fullName']} ({pos}, {team})"


def find_player(name: str) -> dict:
    resp = requests.get(
        f"{API_BASE}/people/search",
        params={"names": name, "hydrate": "currentTeam"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    people = [p for p in resp.json().get("people", []) if p.get("active")]

    if not people:
        sys.exit(f"No active player found matching '{name}'.")
    exact = [p for p in people if _norm(p["fullName"]) == _norm(name)]
    candidates = exact or people
    if len(candidates) > 1:
        options = "; ".join(_describe(p) for p in candidates[:8])
        sys.exit(
            f"'{name}' matches multiple active players: {options}. "
            f"Please be more specific (full name, suffix, or accented spelling)."
        )
    return candidates[0]


def get_season_stats(player_id: int, season: int) -> dict:
    """Returns {'hitting': {...}, 'pitching': {...}} for whichever groups the player has."""
    resp = requests.get(
        f"{API_BASE}/people/{player_id}/stats",
        params={"stats": "season", "season": season, "group": "hitting,pitching"},
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    out = {}
    for block in resp.json().get("stats", []):
        if block["splits"]:
            out[block["group"]["displayName"]] = block["splits"][0]["stat"]
    return out


def to_scoring_stats(raw: dict, group: str) -> dict:
    if group == "hitting":
        stats = {code: raw.get(api, 0) for api, code in BATTING_MAP.items()}
        stats["1B"] = raw.get("hits", 0) - stats["2B"] - stats["3B"] - stats["HR"]
        return stats
    stats = {code: raw.get(api, 0) for api, code in PITCHING_MAP.items()}
    stats["IP"] = _parse_innings(raw.get("inningsPitched", "0.0"))
    return stats


def print_group(group: str, weights: dict, p1: dict, p2: dict, name1: str, name2: str):
    b1 = breakdown(to_scoring_stats(p1, group), weights)
    b2 = breakdown(to_scoring_stats(p2, group), weights)

    print(f"\n{'=' * 74}\n{group.upper()} — points by category\n{'=' * 74}")
    header = f"{'Category':<18}{'Wt':>6} | {name1[:16]:>16} {'Pts':>8} | {name2[:16]:>16} {'Pts':>8}"
    print(header)
    print("-" * len(header))
    for stat, weight in weights.items():
        c1, pts1 = b1[stat]
        c2, pts2 = b2[stat]
        label = STAT_LABELS.get(stat, stat)
        print(f"{label:<18}{weight:>6} | {c1:>16.1f} {pts1:>8.1f} | {c2:>16.1f} {pts2:>8.1f}")
    t1 = sum(p for _, p in b1.values())
    t2 = sum(p for _, p in b2.values())
    print("-" * len(header))
    print(f"{'TOTAL':<24} | {'':>16} {t1:>8.1f} | {'':>16} {t2:>8.1f}")
    return t1, t2


def main():
    parser = argparse.ArgumentParser(description="Head-to-head fantasy comparison")
    parser.add_argument("player1")
    parser.add_argument("player2")
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    pl1, pl2 = find_player(args.player1), find_player(args.player2)
    name1, name2 = pl1["fullName"], pl2["fullName"]
    print(f"Comparing {name1} vs {name2} — {args.season} season")

    s1, s2 = get_season_stats(pl1["id"], args.season), get_season_stats(pl2["id"], args.season)
    for name, stats in ((name1, s1), (name2, s2)):
        if not stats:
            sys.exit(f"{name} has no {args.season} MLB stats — possibly the wrong player, "
                     f"a minor leaguer, or someone who hasn't played this season.")

    total1 = total2 = 0.0
    shared = [g for g in ("hitting", "pitching") if g in s1 or g in s2]
    if not shared:
        sys.exit(f"Neither player has {args.season} stats.")
    for group in shared:
        weights = BATTING_WEIGHTS if group == "hitting" else PITCHING_WEIGHTS
        t1, t2 = print_group(group, weights, s1.get(group, {}), s2.get(group, {}), name1, name2)
        total1 += t1
        total2 += t2

    print(f"\n{'=' * 74}")
    if total1 == total2:
        print(f"DEAD EVEN: both at {total1:.1f} fantasy points.")
    else:
        leader, trailer = (name1, name2) if total1 > total2 else (name2, name1)
        margin = abs(total1 - total2)
        print(f"VERDICT: {leader} leads {trailer} by {margin:.1f} fantasy points "
              f"({max(total1, total2):.1f} to {min(total1, total2):.1f}).")
    if any("pitching" in s for s in (s1, s2)):
        print("Note: Quality Starts not available from the MLB Stats API; scored as 0.")


if __name__ == "__main__":
    main()
