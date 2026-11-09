"""Calculations for the dashboard cards and charts.

Pure pandas, no Streamlit imports, so it can be tested on its own.
Everything here works on the filtered DataFrame returned by the /data endpoint.
"""
from __future__ import annotations

import pandas as pd

MISSING = "\u2014"  # shown when a value cannot be calculated

# label, column, aggregation, formatter, st.metric delta_color
KPI_SPECS = [
    ("Total campaigns", None, "count", lambda v: f"{v:,.0f}", "normal"),
    ("Avg ROI", "ROI", "mean", lambda v: f"{v:.2f}x", "normal"),
    ("Avg conversion rate", "Conversion_Rate", "mean", lambda v: f"{v * 100:.2f}%", "normal"),
    # Lower acquisition cost is better, so an increase shows in the "bad" color.
    ("Avg acquisition cost", "Acquisition_Cost", "mean", lambda v: f"${v:,.2f}", "inverse"),
    ("Total clicks", "Clicks", "sum", lambda v: f"{v:,.0f}", "normal"),
    ("Avg engagement score", "Engagement_Score", "mean", lambda v: f"{v:.2f}", "normal"),
]


def _aggregate(frame: pd.DataFrame, column: str | None, how: str) -> float | None:
    if how == "count":
        return float(len(frame))
    values = pd.to_numeric(frame[column], errors="coerce")
    result = values.mean() if how == "mean" else values.sum()
    return None if pd.isna(result) else float(result)


def _quarter_change(df: pd.DataFrame, column: str | None, how: str) -> float | None:
    """Percent change between the latest quarter and the quarter before it.

    Returns None when the Date column is missing, there are fewer than two
    quarters, the quarters are not consecutive, or the earlier value is zero.
    Totals (count, sum) return None when the latest quarter is incomplete.
    """
    if "Date" not in df.columns:
        return None
    quarters = pd.to_datetime(df["Date"], errors="coerce").dt.to_period("Q")
    periods = sorted(quarters.dropna().unique())
    if len(periods) < 2:
        return None
    current, previous = periods[-1], periods[-2]
    if previous + 1 != current:
        return None
    if how in ("count", "sum"):
        # Totals are only comparable when the latest quarter is complete.
        latest_date = pd.to_datetime(df["Date"], errors="coerce").max()
        if latest_date < current.end_time.normalize():
            return None
    now = _aggregate(df[quarters == current], column, how)
    before = _aggregate(df[quarters == previous], column, how)
    if now is None or not before:
        return None
    return (now - before) / abs(before) * 100


def compute_kpis(df: pd.DataFrame) -> list[dict]:
    """One dict per KPI card: label, value text, delta text (or None), delta color."""
    cards = []
    for label, column, how, fmt, delta_color in KPI_SPECS:
        value, delta = None, None
        usable = not df.empty and (column is None or column in df.columns)
        if usable:
            raw = _aggregate(df, column, how)
            if raw is not None:
                value = fmt(raw)
            change = _quarter_change(df, column, how)
            if change is not None:
                delta = f"{change:+.1f}% vs prev Q"
        cards.append({"label": label, "value": value or MISSING, "delta": delta, "delta_color": delta_color})
    return cards


def top_by_roi(df: pd.DataFrame, group_col: str, n: int = 5) -> pd.DataFrame:
    """Top n categories by average ROI, highest first."""
    if df.empty or group_col not in df.columns or "ROI" not in df.columns:
        return pd.DataFrame(columns=[group_col, "ROI"])
    roi = pd.to_numeric(df["ROI"], errors="coerce")
    out = roi.groupby(df[group_col]).mean().dropna().sort_values(ascending=False).head(n)
    return out.rename("ROI").rename_axis(group_col).reset_index()


def share_by(df: pd.DataFrame, group_col: str, max_slices: int = 6) -> pd.DataFrame:
    """Campaign counts per category. Extra categories are grouped as 'Other'."""
    if df.empty or group_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "Campaigns"])
    counts = df[group_col].value_counts()
    if len(counts) > max_slices:
        head = counts.iloc[: max_slices - 1]
        counts = pd.concat([head, pd.Series({"Other": counts.iloc[max_slices - 1:].sum()})])
    return counts.rename("Campaigns").rename_axis(group_col).reset_index()
