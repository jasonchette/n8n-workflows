# Fantasy Baseball Points Engine

Pulls current-season MLB stats via `pybaseball` and ranks every player by your
CBS league's points formula (see `scoring.py` for the exact weights).

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
sorted highest to lowest.

## Notes

- `QS` (Quality Starts) and `HLD` (Holds) aren't part of FanGraphs' default
  pitching stat pull. If they're missing from the output, `scoring.py` will
  print a warning and score them as 0 rather than fail — those two columns
  will need to be added from a specific FanGraphs leaderboard view.
- `--qual 0` (the default) includes every player, even part-timers. Raise it
  (e.g. `--qual 100`) to only include players with a minimum number of
  plate appearances / innings pitched.
