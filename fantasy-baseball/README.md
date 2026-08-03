# Fantasy Baseball Points Engine

Pulls current-season MLB stats and ranks every player by your CBS league's
points formula (see `scoring.py` for the exact weights).

## Data source note

This originally used `pybaseball` (which scrapes FanGraphs). FanGraphs now
sits behind a Cloudflare bot challenge that blocks automated requests, so
the data pull was switched to the **official MLB Stats API**
(`statsapi.mlb.com`) instead — a public, structured, non-scraped source with
no bot protection. `pybaseball` is no longer a dependency of this script,
though it may come back for future features that use Statcast (Baseball
Savant, which is reachable) or its player-ID lookup utility.

One tradeoff: the MLB Stats API doesn't expose **Quality Starts** as a
season aggregate stat. `scoring.py` scores it as 0 for now and prints a
warning — computing it for real would mean pulling every pitcher's game log
and checking each start against the QS rule (6+ IP, 3 or fewer ER), which is
a reasonable next step but more work than the other categories. Holds *are*
available and are already wired up correctly.

## Setup

```
cd fantasy-baseball
pip install -r requirements.txt
```

## Run: full-league rankings

```
python pull_fantasy_points.py --season 2026
```

This writes two ranked CSVs to `output/`:
- `batting_fantasy_points_2026.csv`
- `pitching_fantasy_points_2026.csv`

Each row is a player with their raw stats plus a `FantasyPoints` column,
sorted highest to lowest. Includes every player who has appeared in a game
this season (no minimum PA/IP cutoff), so part-timers and September-type
call-ups are included alongside regulars.

## Run: overrated / underrated finder

```
python overrated_underrated.py --season 2026
```

Pulls consensus ADP (average draft position) from FantasyPros, computes every
drafted player's actual fantasy points, ranks both, and reports the gap:

- **RankDelta = ADP rank − production rank.** Positive means the player is
  outproducing their draft cost (underrated); negative means they were
  drafted high and are under-delivering (overrated).
- Prints the top 15 of each list and writes the full table to
  `output/adp_value_deltas_<season>.csv`, including each player's CBS-specific
  ADP alongside the consensus.
- The printed lists apply a playing-time floor (default 100 PA / 30 IP,
  adjustable with `--min-pa` / `--min-ip`) so season-long injuries and
  demotions don't drown out actionable names; the CSV keeps everyone, with a
  Status column (IL60, MiLB, etc.) explaining absences.
- Name differences between sources (accents, suffixes like "Jr."/"II") are
  handled automatically; players FantasyPros lists who have no MLB stats this
  season are counted and noted rather than silently dropped.

## Run: head-to-head comparison

```
python compare_players.py "Yordan Alvarez" "James Wood" --season 2026
```

Looks up both players by name, pulls their season stats, and prints a
side-by-side table showing each scoring category — the count, and the
fantasy points it produced — plus a total and verdict line.

Details worth knowing:
- Two-way players (e.g. Shohei Ohtani) get both their hitting and pitching
  points counted in their total.
- If a name matches more than one active player (e.g. "Luis Garcia"), the
  script lists the candidates with position and team, and asks you to be
  more specific — it will never silently guess. Accents and suffixes both
  work for narrowing it down ("Luis García Jr.").
- Name matching is accent- and case-insensitive.
