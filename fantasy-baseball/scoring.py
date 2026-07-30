"""CBS league fantasy points formula, applied to pybaseball stat tables."""

import pandas as pd

BATTING_WEIGHTS = {
    "1B": 1,
    "2B": 2,
    "3B": 3,
    "HR": 4,
    "BB": 1,
    "HBP": 1,
    "R": 1,
    "RBI": 1,
    "SB": 2,
    "CS": -1,
    "SO": -0.5,
}

PITCHING_WEIGHTS = {
    "IP": 3.5,
    "SO": 1,
    "QS": 2,
    "SV": 6,
    "HLD": 6,
    "BB": -0.75,
    "HBP": -0.75,
    "ER": -1.5,
    "H": -1.5,
}


def _score(df: pd.DataFrame, weights: dict) -> pd.Series:
    missing = [stat for stat in weights if stat not in df.columns]
    if missing:
        print(f"Warning: stat(s) not found in pull, scored as 0: {missing}")
    return sum(df[stat] * weight for stat, weight in weights.items() if stat in df.columns)


def add_batting_points(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a derived '1B' column and a 'FantasyPoints' column to a batting stat table."""
    df = df.copy()
    df["1B"] = df["H"] - df["2B"] - df["3B"] - df["HR"]
    df["FantasyPoints"] = _score(df, BATTING_WEIGHTS)
    return df


def add_pitching_points(df: pd.DataFrame) -> pd.DataFrame:
    """Adds a 'FantasyPoints' column to a pitching stat table."""
    df = df.copy()
    df["FantasyPoints"] = _score(df, PITCHING_WEIGHTS)
    return df
