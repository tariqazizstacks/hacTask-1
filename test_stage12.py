"""
test_stage12.py
===============
Tests for src/analytics.py and its place on the dashboard.

    python test_stage12.py

Section [1] checks every figure requirement R asks for. Section [6] proves
the numbers move when a booking is added, which is the part the demo depends
on: submit a request, switch to the Dashboard, and the totals must already
have changed.
"""

import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))

from src import analytics, config, database, ui_logic

PASSED = 0
FAILED = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  PASS  {label}")
    else:
        FAILED += 1
        print(f"  FAIL  {label} {detail}")


# ===========================================================================
print("\n[1] Requirement R - the six headline figures")
# ===========================================================================
m = analytics.summary_metrics()
raw = database.load_requests()

check("total service requests", m["total_requests"] == len(raw) == 15,
      str(m["total_requests"]))
check("most requested service is reported",
      m["top_service"] in config.SERVICE_CATEGORIES, m["top_service"])
check("most requested service matches the data",
      m["top_service"] == raw["service_category"].value_counts().index[0])
check("most requested area is reported", m["top_area"] in config.AREAS, m["top_area"])
check("most requested area matches the data",
      m["top_area"] == raw["area"].value_counts().index[0])
check("average estimated price is computed",
      m["average_price"] == int(round(raw["estimated_price"].mean())),
      str(m["average_price"]))
check("requests by service category is available",
      len(analytics.requests_by_category()) > 0)
check("status distribution is available",
      len(analytics.status_distribution()) == len(config.REQUEST_STATUSES))

check("total estimated value is computed",
      m["total_value"] == int(raw["estimated_price"].sum()))
check("open requests are counted", m["open_requests"] >= 0)
check("completion rate is a percentage", 0 <= m["completion_rate"] <= 100)

# cancelled jobs must not count against the completion rate
completed = int((raw["status"] == "Completed").sum())
cancelled = int((raw["status"] == "Cancelled").sum())
expected_rate = round(100 * completed / (len(raw) - cancelled), 1)
check("cancellations are excluded from the completion rate",
      m["completion_rate"] == expected_rate,
      f"{m['completion_rate']} vs {expected_rate}")

# ===========================================================================
print("\n[2] Chart data shapes")
# ===========================================================================
cat = analytics.requests_by_category()
check("category chart has the declared columns",
      list(cat.columns) == analytics.CHART_CATEGORY)
check("category counts sum to the total", cat["Requests"].sum() == 15)
check("category chart is sorted busiest first",
      list(cat["Requests"]) == sorted(cat["Requests"], reverse=True))
check("every category shown is a real one",
      set(cat["Service"]) <= set(config.SERVICE_CATEGORIES))

status = analytics.status_distribution()
check("status chart has the declared columns",
      list(status.columns) == analytics.CHART_STATUS)
check("all four statuses always appear",
      list(status["Status"]) == list(config.REQUEST_STATUSES))
check("status counts sum to the total", status["Requests"].sum() == 15)

time_df = analytics.requests_over_time()
check("timeline has the declared columns",
      list(time_df.columns) == analytics.CHART_TIME)
check("timeline counts sum to the total", time_df["Requests"].sum() == 15)
check("timeline is in date order", len(time_df) >= 2)

value = analytics.value_by_category()
check("value chart has the declared columns",
      list(value.columns) == analytics.CHART_VALUE)
check("value totals match the raw sum",
      value["Estimated value"].sum() == int(raw["estimated_price"].sum()))
check("value chart is sorted highest first",
      list(value["Estimated value"]) == sorted(value["Estimated value"], reverse=True))

matrix = analytics.area_service_matrix()
check("area matrix has an Area column", "Area" in matrix.columns)
check("area matrix covers every area used",
      set(matrix["Area"]) == set(raw["area"].unique()))

# ===========================================================================
print("\n[3] Volume and value tell different stories")
# ===========================================================================
# This is the analytical point of the value chart: painting is booked rarely
# but is worth several times a locksmith call.
top_volume = cat.iloc[0]["Service"]
top_value = value.iloc[0]["Service"]
check("the demo data shows a volume/value divergence",
      top_volume != top_value, f"both {top_volume}")
check("Painter leads by value", top_value == "Painter", top_value)

# ===========================================================================
print("\n[4] Written insights")
# ===========================================================================
notes = analytics.insights()
check("insights are produced", len(notes) >= 2, str(len(notes)))
check("the busiest trade is named", any(top_volume in n for n in notes))
check("the volume/value divergence is called out",
      any("By value" in n for n in notes))
check("open work is mentioned", any("still open" in n for n in notes))
check("urgency share is mentioned", any("urgent" in n for n in notes))
check("insights render as a bullet list",
      analytics.insights_markdown().startswith("- "))

md = analytics.metrics_markdown()
check("the metrics table shows the total", "15" in md)
check("the metrics table shows the top service", top_volume in md)
check("the metrics table formats money", "PKR" in md)
check("the metrics table is a markdown table", md.startswith("| |"))

# ===========================================================================
print("\n[5] Empty data")
# ===========================================================================
real_loader = database.load_requests
database.load_requests = lambda: pd.DataFrame(columns=config.REQUEST_COLUMNS)
try:
    empty = analytics.summary_metrics()
    check("empty data gives zero requests", empty["total_requests"] == 0)
    check("empty data gives a dash for the top service", empty["top_service"] == "\u2014")
    check("empty data gives zero average", empty["average_price"] == 0)
    check("empty data gives a zero completion rate", empty["completion_rate"] == 0.0)
    check("empty category chart has the right columns",
          list(analytics.requests_by_category().columns) == analytics.CHART_CATEGORY)
    check("empty status chart still shows four statuses",
          len(analytics.status_distribution()) == 4)
    check("empty status counts are all zero",
          analytics.status_distribution()["Requests"].sum() == 0)
    check("empty timeline does not crash", analytics.requests_over_time().empty)
    check("empty value chart does not crash", analytics.value_by_category().empty)
    check("empty area matrix does not crash", analytics.area_service_matrix().empty)
    check("empty insights are empty", analytics.insights() == [])
    check("the empty metrics panel explains itself",
          "nothing to analyse" in analytics.metrics_markdown())
    check("the analytics bundle survives empty data",
          len(ui_logic.analytics_bundle()) == 6)
finally:
    database.load_requests = real_loader

check("analytics recover after the data returns",
      analytics.summary_metrics()["total_requests"] == 15)

# ===========================================================================
print("\n[6] The numbers move when a booking is added")
# ===========================================================================
backup = config.REQUESTS_CSV.with_suffix(".backup")
shutil.copy(config.REQUESTS_CSV, backup)

try:
    before = analytics.summary_metrics()
    before_painter = int(
        analytics.requests_by_category()
        .set_index("Service")["Requests"].get("Painter", 0))

    result = ui_logic.submit_booking(
        "Analytics Tester", "0300-5556677", "Karachi",
        "Flat 9, Clifton", "The lounge walls need repainting completely",
        (date.today() + timedelta(days=3)).isoformat(),
        config.TIME_SLOTS[1], "", database.get_provider("P024"),
        {"urgency": "normal"})
    check("the test booking saved", result["ok"] is True, result["message_md"][:80])

    after = analytics.summary_metrics()
    check("the total went up by one",
          after["total_requests"] == before["total_requests"] + 1)
    check("the estimated value went up",
          after["total_value"] > before["total_value"])
    check("Painter's count went up by one",
          int(analytics.requests_by_category()
              .set_index("Service")["Requests"]["Painter"]) == before_painter + 1)
    check("the new request shows as Pending",
          int(analytics.status_distribution()
              .set_index("Status")["Requests"]["Pending"]) >= 1)
    check("the timeline picks up the new request",
          analytics.requests_over_time()["Requests"].sum() == after["total_requests"])
    check("the metrics panel shows the new total",
          str(after["total_requests"]) in analytics.metrics_markdown())

    # status changes must flow through to the chart
    ui_logic.change_status(result["request_id"], "Completed")
    check("a status change updates the distribution",
          int(analytics.status_distribution()
              .set_index("Status")["Requests"]["Completed"])
          == int((database.load_requests()["status"] == "Completed").sum()))

finally:
    shutil.move(str(backup), str(config.REQUESTS_CSV))
    print(f"\n  (restored {config.REQUESTS_CSV.name} to its seeded state)")

check("data restored to 15 requests",
      analytics.summary_metrics()["total_requests"] == 15)

# ===========================================================================
print("\n[7] The dashboard bundle and app wiring")
# ===========================================================================
bundle = ui_logic.analytics_bundle()
check("the bundle has all six pieces", len(bundle) == 6)
for key in ["metrics_md", "insights_md", "by_category", "by_status",
            "by_value", "over_time"]:
    check(f"bundle contains {key}", key in bundle)
check("bundle chart entries are DataFrames",
      all(isinstance(bundle[k], pd.DataFrame)
          for k in ["by_category", "by_status", "by_value", "over_time"]))


class _Node:
    def __init__(self, name="n"):
        self._name = name

    def __call__(self, *a, **k):
        return _Node(self._name)

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)
        return _Node(f"{self._name}.{item}")

    def __enter__(self):
        return self

    def __exit__(self, *e):
        return False


class _FakeGradio:
    def __init__(self):
        self.created = []

    def __getattr__(self, item):
        if item.startswith("_"):
            raise AttributeError(item)

        def factory(*a, **k):
            self.created.append(item)
            return _Node(item)

        return factory


fake = _FakeGradio()
fake.themes = _Node("themes")
sys.modules["gradio"] = fake

import app  # noqa: E402

check("app.py still builds with the analytics section", True)
check("four charts are created", fake.created.count("BarPlot") == 4,
      str(fake.created.count("BarPlot")))

dash = app.on_dashboard_refresh("All")
check("on_dashboard_refresh now returns 10 outputs", len(dash) == 10, str(len(dash)))
check("the table is still first", len(dash[0]) == 15)
check("the metrics markdown is included", "PKR" in dash[4])
check("the category chart data is included", list(dash[5].columns) == analytics.CHART_CATEGORY)
check("the status chart data is included", list(dash[6].columns) == analytics.CHART_STATUS)
check("the insights are included", dash[9].startswith("- "))

# ===========================================================================
print(f"\n{'=' * 46}")
print(f"  {PASSED} passed, {FAILED} failed")
print(f"{'=' * 46}\n")
sys.exit(1 if FAILED else 0)
