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

## Run

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
