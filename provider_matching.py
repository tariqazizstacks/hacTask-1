"""
src/provider_matching.py
========================
Ranks providers for a customer request. Pure Pandas -- no LLM anywhere near
this file.

That separation is the heart of the project. The language model reads the
customer's words; this module decides who gets recommended, using data from
providers.csv and arithmetic you can check by hand. When an examiner asks
"how do you know the AI isn't making up these providers?", the answer is
that the AI never sees them.

HOW THE SCORE WORKS
-------------------
Service category is a HARD FILTER, not a score. A plumber is never a valid
answer to an AC problem no matter how good their rating, so non-matching
categories are removed before any scoring happens.

The survivors are scored out of 100 using the weights in config.py:

    area          30   right trade in the wrong city is useless
    rating        30   quality signal
    availability  20   only really matters when the job is urgent
    price         20   only scored when the customer gave a budget

Two ideas worth understanding:

  NEUTRAL CREDIT. When a factor does not apply -- no budget given, or the job
  is not urgent -- every provider receives 75% of that weight rather than 0.
  Scoring everyone 0 would be mathematically equivalent but would make the
  displayed score look artificially low, and customers read 62/100 as "bad".

  GRACEFUL DEGRADATION. If nobody serves the customer's area, we do not show
  an empty screen. The area filter is dropped, the search re-runs, and the
  result is clearly labelled as out-of-area.

Public API:
    find_providers(slots, top_n=3)      -> dict with a ranked DataFrame
    filter_providers(category, ...)     -> DataFrame  (manual browse tab)
    explain_score(row)                  -> str
    score_breakdown_markdown(row)       -> str

Imports from: config.py, database.py, utils.py
Used by: app.py
"""

from __future__ import annotations

import pandas as pd

from . import config, database, utils

W = config.SCORING_WEIGHTS

# Availability points when the job IS urgent. When it is not, every provider
# gets neutral credit instead -- see _score_availability.
URGENT_AVAILABILITY_POINTS = {
    "Today": 1.0,
    "Tomorrow": 0.5,
    "Within 3 Days": 0.2,
    "Weekends Only": 0.0,
}


# ===========================================================================
# INDIVIDUAL FACTOR SCORES
# ===========================================================================
# Each returns (points, explanation). Keeping the explanation next to the
# arithmetic is what makes the breakdown on the card trustworthy -- the text
# cannot drift away from the number because they are produced together.

def _score_area(provider_area: str, wanted: str | None) -> tuple[float, str]:
    if not wanted:
        # No area given yet. Neutral credit: we cannot fault a provider for
        # information the customer has not supplied.
        return W["area"] * config.NEUTRAL_CREDIT, "no area given yet"
    if provider_area == wanted:
        return W["area"], f"based in {provider_area}"
    if utils.same_region(provider_area, wanted):
        return (W["area"] * config.SAME_REGION_CREDIT,
                f"{provider_area}, near {wanted}")
    return 0.0, f"{provider_area}, outside {wanted}"


def _score_rating(rating) -> tuple[float, str]:
    try:
        value = float(rating)
    except (TypeError, ValueError):
        return 0.0, "not rated"
    return (value / 5.0) * W["rating"], f"{value:.1f} out of 5"


def _score_availability(availability: str, urgency: str) -> tuple[float, str]:
    if urgency in ("emergency", "urgent"):
        share = URGENT_AVAILABILITY_POINTS.get(availability, 0.0)
        return W["availability"] * share, f"available {availability.lower()}"
    # Not urgent: availability barely matters, so do not punish a good
    # provider for being booked until Thursday.
    return (W["availability"] * config.NEUTRAL_CREDIT,
            f"available {availability.lower()}")


def _score_price(price_min, price_max, budget) -> tuple[float, str]:
    if not budget:
        return W["price"] * config.NEUTRAL_CREDIT, "no budget set"
    try:
        low, high, cap = float(price_min), float(price_max), float(budget)
    except (TypeError, ValueError):
        return W["price"] * config.NEUTRAL_CREDIT, "price unclear"

    if high <= cap:
        return W["price"], "fully within your budget"
    if low > cap:
        return 0.0, "above your budget"
    # Partly inside: credit the proportion of their range that fits.
    span = max(high - low, 1.0)
    share = (cap - low) / span
    return W["price"] * share, "partly within your budget"


# ===========================================================================
# SCORING ONE PROVIDER
# ===========================================================================

def score_provider(provider: dict, area: str | None, urgency: str,
                   budget=None) -> dict:
    """Score one provider and return the parts as well as the total."""
    area_pts, area_why = _score_area(provider.get("area"), area)
    rating_pts, rating_why = _score_rating(provider.get("rating"))
    avail_pts, avail_why = _score_availability(
        provider.get("availability", ""), urgency)
    price_pts, price_why = _score_price(
        provider.get("price_min"), provider.get("price_max"), budget)

    total = area_pts + rating_pts + avail_pts + price_pts
    return {
        "score": round(total, 1),
        "score_area": round(area_pts, 1),
        "score_rating": round(rating_pts, 1),
        "score_availability": round(avail_pts, 1),
        "score_price": round(price_pts, 1),
        "why_area": area_why,
        "why_rating": rating_why,
        "why_availability": avail_why,
        "why_price": price_why,
    }


# ===========================================================================
# SEARCH
# ===========================================================================

def _rank(df: pd.DataFrame, area, urgency, budget, top_n) -> pd.DataFrame:
    """Score, sort deterministically, and cut to the top N."""
    if df.empty:
        return df

    scored = df.copy()
    parts = scored.apply(
        lambda row: score_provider(row.to_dict(), area, urgency, budget),
        axis=1, result_type="expand",
    )
    scored = pd.concat([scored, parts], axis=1)

    # Deterministic ordering matters more than it sounds: without the final
    # provider_id tiebreak, two providers on the same score could swap places
    # between runs and your demo would not reproduce.
    scored = scored.sort_values(
        by=["score", "rating", "experience_years", "provider_id"],
        ascending=[False, False, False, True],
    ).reset_index(drop=True)

    return scored.head(top_n) if top_n else scored


def find_providers(slots: dict, top_n: int = None, budget=None) -> dict:
    """
    The main entry point. Never raises.

    Returns:
        providers   ranked DataFrame (may be empty)
        count       how many are being returned
        total_in_category   how many exist for that category at all
        relaxed     True when the area filter had to be dropped
        message     user-facing explanation, or "" when a normal match
        category    the category searched
        area        the area searched

    NOTE ON THE CONTRACT: the roadmap said this would return a bare
    DataFrame. It returns a dict instead, because the UI needs to know
    whether the area filter was relaxed in order to label the results
    honestly, and re-deriving that in app.py would duplicate the logic.
    """
    top_n = top_n or config.TOP_N_PROVIDERS
    slots = slots or {}
    category = slots.get("service_category")
    area = slots.get("area")
    urgency = slots.get("urgency", "normal")
    budget = budget if budget is not None else slots.get("budget_max")

    blank = {
        "providers": pd.DataFrame(),
        "count": 0,
        "total_in_category": 0,
        "in_area": 0,
        "relaxed": False,
        "message": "",
        "category": category,
        "area": area,
    }

    if category not in config.SERVICE_CATEGORIES:
        blank["message"] = (
            "I could not work out which service you need, so I cannot search "
            "yet. Tell me what is wrong and which item it affects."
        )
        return blank

    try:
        everyone = database.load_providers()
    except Exception as exc:                      # database already guards,
        blank["message"] = f"Could not load the provider list: {exc}"
        return blank                              # this is belt and braces

    if everyone.empty:
        blank["message"] = (
            "The provider list is empty. Run generate_data.py to create it."
        )
        return blank

    in_category = everyone[everyone["service_category"] == category]
    blank["total_in_category"] = len(in_category)

    if in_category.empty:
        blank["message"] = (
            f"We do not have any {category} providers in the demo dataset yet."
        )
        return blank

    # --- rank the whole category ---------------------------------------
    # Area is a 30-point WEIGHT, not a filter. Filtering on it starves the
    # results: only one AC technician in the demo data is based in Islamabad,
    # so a strict filter would show a single card where the customer expects
    # a choice. Scoring instead puts the local provider top and still offers
    # nearby alternatives underneath.
    in_area = in_category[in_category["area"] == area] if area else in_category
    none_in_area = bool(area) and in_area.empty

    ranked = _rank(in_category, area, urgency, budget, top_n)

    message = ""
    if none_in_area:
        message = (
            f"No {category} providers are listed in {area} in our demo data, "
            f"so these are the closest matches from other areas."
        )
    elif area and len(in_area) < top_n:
        extra = len(ranked) - len(in_area)
        if extra > 0:
            message = (
                f"Only {len(in_area)} {category} "
                f"{'provider is' if len(in_area) == 1 else 'providers are'} "
                f"listed in {area}, so nearby options are shown too."
            )

    return {
        "providers": ranked,
        "count": len(ranked),
        "total_in_category": len(in_category),
        "in_area": len(in_area),
        "relaxed": none_in_area,
        "message": message,
        "category": category,
        "area": area,
    }


def filter_providers(category: str = None, area: str = None,
                     availability: str = None, min_rating: float = None,
                     max_price: float = None) -> pd.DataFrame:
    """
    Plain filtering for the "Find a Professional" browse tab, where the
    customer picks from dropdowns instead of describing a problem.

    No scoring here on purpose -- browsing is not the same as matching, and
    a relevance score would be meaningless without a stated problem.
    Sorted by rating so the list is still useful.
    """
    try:
        df = database.load_providers()
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df

    if category and category in config.SERVICE_CATEGORIES:
        df = df[df["service_category"] == category]
    if area and area in config.AREAS:
        df = df[df["area"] == area]
    if availability and availability in config.AVAILABILITY_OPTIONS:
        df = df[df["availability"] == availability]
    if min_rating is not None:
        try:
            df = df[df["rating"] >= float(min_rating)]
        except (TypeError, ValueError):
            pass
    if max_price is not None:
        try:
            df = df[df["price_min"] <= float(max_price)]
        except (TypeError, ValueError):
            pass

    return df.sort_values(
        by=["rating", "experience_years"], ascending=[False, False]
    ).reset_index(drop=True)


# ===========================================================================
# EXPLANATIONS
# ===========================================================================

def explain_score(row) -> str:
    """One-line summary for the provider card."""
    row = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    bits = [row.get("why_area"), row.get("why_rating"), row.get("why_availability")]
    return " \u00b7 ".join(b for b in bits if b)


def score_breakdown_markdown(row) -> str:
    """
    The full arithmetic, for the expandable detail on each card.

    Requirement E asks for a transparent scoring system. Showing the numbers
    is what makes it transparent -- a score with no breakdown is just a
    different kind of black box.
    """
    row = row.to_dict() if hasattr(row, "to_dict") else dict(row)
    lines = [
        "| Factor | Points | Why |",
        "| --- | --- | --- |",
        f"| Area | {row.get('score_area', 0)} / {W['area']} | {row.get('why_area', '')} |",
        f"| Rating | {row.get('score_rating', 0)} / {W['rating']} | {row.get('why_rating', '')} |",
        f"| Availability | {row.get('score_availability', 0)} / {W['availability']} | {row.get('why_availability', '')} |",
        f"| Price | {row.get('score_price', 0)} / {W['price']} | {row.get('why_price', '')} |",
        f"| **Total** | **{row.get('score', 0)} / 100** | |",
    ]
    return "\n".join(lines)


# ===========================================================================
# Self-check: python -m src.provider_matching
# ===========================================================================
if __name__ == "__main__":
    cases = [
        {"service_category": "AC Technician", "area": "Islamabad", "urgency": "urgent"},
        {"service_category": "Plumber", "area": "Karachi", "urgency": "normal"},
        {"service_category": "AC Technician", "area": "Hyderabad", "urgency": "urgent"},
    ]
    for slots in cases:
        result = find_providers(slots)
        print(f"\n{slots['service_category']} in {slots['area']} "
              f"({slots['urgency']}) -> {result['count']} of "
              f"{result['total_in_category']}")
        if result["message"]:
            print(f"  note: {result['message']}")
        for _, row in result["providers"].iterrows():
            print(f"  {row['score']:>5}  {row['provider_name']:<26} "
                  f"{row['area']:<11} {row['rating']} "
                  f"{row['availability']:<14} {explain_score(row)}")
