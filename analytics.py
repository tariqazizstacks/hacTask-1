"""
src/analytics.py
================
The business analytics half of the project (requirement R).

Everything here reads data/requests.csv through database.load_requests() and
returns either a plain dict of numbers or a small tidy DataFrame ready to
plot. No charting library is imported: the Gradio BarPlot component draws
directly from a DataFrame, which keeps this module testable and avoids a
matplotlib dependency that would only be used in one place.

Each function answers a question a service manager would actually ask:

    summary_metrics()        how much work is coming in, and from where
    requests_by_category()   which trades are in demand
    status_distribution()    how much work is still outstanding
    requests_over_time()     is demand growing
    value_by_category()      where the money is
    area_service_matrix()    which trade is needed in which area
    insights()               the three things worth saying out loud

Never raises. An empty requests.csv produces zeros and empty frames, not an
exception, because the dashboard renders before anyone has booked anything.

Imports from: config, database, utils
Used by: ui_logic (dashboard tab)
"""

from __future__ import annotations

import pandas as pd

from . import config, database, utils

CHART_CATEGORY = ["Service", "Requests"]
CHART_STATUS = ["Status", "Requests"]
CHART_TIME = ["Week", "Requests"]
CHART_VALUE = ["Service", "Estimated value"]


def _requests() -> pd.DataFrame:
    df = database.load_requests()
    if df.empty:
        return df
    df = df.copy()
    df["estimated_price"] = pd.to_numeric(
        df["estimated_price"], errors="coerce").fillna(0)
    # errors="coerce" rather than a hard parse: a hand-edited CSV with one
    # malformed date should cost us that row's timeline entry, not the whole
    # analytics tab.
    df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
    return df


# ===========================================================================
# HEADLINE METRICS
# ===========================================================================

def summary_metrics() -> dict:
    """The six figures requirement R asks for, plus two that earn their place."""
    df = _requests()
    empty = {
        "total_requests": 0,
        "top_service": "\u2014", "top_service_count": 0,
        "top_area": "\u2014", "top_area_count": 0,
        "average_price": 0, "total_value": 0,
        "open_requests": 0, "completion_rate": 0.0,
    }
    if df.empty:
        return empty

    services = df["service_category"].value_counts()
    areas = df["area"].value_counts()
    statuses = df["status"].value_counts()

    completed = int(statuses.get("Completed", 0))
    cancelled = int(statuses.get("Cancelled", 0))
    open_count = len(df) - completed - cancelled

    # Cancelled jobs are excluded from the denominator. A cancellation is not
    # a failure to complete work; counting it as one would make the team look
    # worse the more customers change their minds.
    finished_or_working = len(df) - cancelled

    return {
        "total_requests": len(df),
        "top_service": services.index[0] if len(services) else "\u2014",
        "top_service_count": int(services.iloc[0]) if len(services) else 0,
        "top_area": areas.index[0] if len(areas) else "\u2014",
        "top_area_count": int(areas.iloc[0]) if len(areas) else 0,
        "average_price": int(round(df["estimated_price"].mean())),
        "total_value": int(df["estimated_price"].sum()),
        "open_requests": int(open_count),
        "completion_rate": round(
            100 * completed / finished_or_working, 1) if finished_or_working else 0.0,
    }


def metrics_markdown() -> str:
    """The headline figures as a compact table above the charts."""
    m = summary_metrics()
    if not m["total_requests"]:
        return (
            "No requests recorded yet, so there is nothing to analyse. Submit "
            "a request on the AI Assistant tab and these figures will fill in."
        )
    return f"""| | | |
| --- | --- | --- |
| **{m['total_requests']}** requests | **{m['top_service']}** most requested | **{m['top_area']}** busiest area |
| **{utils.format_price(m['average_price'])}** average job | **{utils.format_price(m['total_value'])}** estimated total | **{m['completion_rate']}%** completed |
"""


# ===========================================================================
# CHART DATA
# ===========================================================================

def requests_by_category() -> pd.DataFrame:
    """Demand per trade, busiest first. Trades with no requests are omitted."""
    df = _requests()
    if df.empty:
        return pd.DataFrame(columns=CHART_CATEGORY)
    counts = df["service_category"].value_counts()
    return pd.DataFrame({
        CHART_CATEGORY[0]: counts.index,
        CHART_CATEGORY[1]: counts.values.astype(int),
    })


def status_distribution() -> pd.DataFrame:
    """
    How much work is outstanding.

    Every status is listed even when its count is zero, so the chart keeps
    the same four bars as requests move between them. A chart whose axis
    changes shape on every refresh is hard to read.
    """
    df = _requests()
    counts = df["status"].value_counts() if not df.empty else pd.Series(dtype=int)
    return pd.DataFrame({
        CHART_STATUS[0]: list(config.REQUEST_STATUSES),
        CHART_STATUS[1]: [int(counts.get(s, 0)) for s in config.REQUEST_STATUSES],
    })


def requests_over_time() -> pd.DataFrame:
    """
    Volume by week. Weekly rather than daily because a student demo has a
    handful of requests spread over a month, and a daily chart of that is
    mostly empty space.
    """
    df = _requests()
    if df.empty or df["created_dt"].isna().all():
        return pd.DataFrame(columns=CHART_TIME)
    dated = df.dropna(subset=["created_dt"]).copy()
    dated["week"] = dated["created_dt"].dt.to_period("W").dt.start_time
    counts = dated.groupby("week").size().sort_index()
    return pd.DataFrame({
        CHART_TIME[0]: [d.strftime("%d %b") for d in counts.index],
        CHART_TIME[1]: counts.values.astype(int),
    })


def value_by_category() -> pd.DataFrame:
    """
    Estimated value per trade, not request count.

    This is the one chart that changes the answer. Painting is booked rarely
    but is worth several times an average locksmith call, so "which trade
    matters most" looks different by volume than by value.
    """
    df = _requests()
    if df.empty:
        return pd.DataFrame(columns=CHART_VALUE)
    totals = df.groupby("service_category")["estimated_price"].sum()
    totals = totals.sort_values(ascending=False)
    return pd.DataFrame({
        CHART_VALUE[0]: totals.index,
        CHART_VALUE[1]: totals.values.astype(int),
    })


def area_service_matrix() -> pd.DataFrame:
    """Requests per area per trade. Useful for spotting coverage gaps."""
    df = _requests()
    if df.empty:
        return pd.DataFrame()
    table = pd.crosstab(df["area"], df["service_category"])
    table.index.name = "Area"
    return table.reset_index()


# ===========================================================================
# INSIGHTS
# ===========================================================================

def insights() -> list[str]:
    """
    Short written observations to sit under the charts.

    A dashboard that only shows numbers leaves the reader to do the analysis.
    For a Business Analytics submission, stating what the numbers mean is
    most of the marks.
    """
    df = _requests()
    if df.empty:
        return []

    m = summary_metrics()
    notes = [
        f"{m['top_service']} is the most requested trade with "
        f"{m['top_service_count']} of {m['total_requests']} requests, so it is "
        f"the first place to add provider capacity."
    ]

    value = value_by_category()
    if not value.empty:
        top_value = value.iloc[0]
        if top_value["Service"] != m["top_service"]:
            notes.append(
                f"By value the picture differs: {top_value['Service']} accounts "
                f"for {utils.format_price(top_value['Estimated value'])} of "
                f"estimated work, more than any other trade, despite not being "
                f"the most frequently requested."
            )

    if m["open_requests"]:
        notes.append(
            f"{m['open_requests']} "
            f"{'request is' if m['open_requests'] == 1 else 'requests are'} "
            f"still open and awaiting completion."
        )

    urgent = int((df["urgency"].isin(["urgent", "emergency"])).sum())
    if urgent:
        share = round(100 * urgent / len(df))
        notes.append(
            f"{share}% of requests were marked urgent or emergency, which is "
            f"why same-day availability carries weight in the ranking."
        )

    return notes


def insights_markdown() -> str:
    notes = insights()
    if not notes:
        return ""
    return "\n".join(f"- {note}" for note in notes)
