import re

from flask import render_template, request, redirect, url_for

from . import ui_bp
from ...extensions import db
from ...models import Search, SearchOrigin, TripType, OriginSubType


_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


@ui_bp.get("/")
def index():
    trip_types = [t.value for t in TripType]
    return render_template("index.html", trip_types=trip_types, error=None)


@ui_bp.post("/searches")
def create_search():
    # ----- read inputs -----
    origins_raw = (request.form.get("origins") or "").upper()
    origin_tokens = [o.strip() for o in origins_raw.split(",") if o.strip()]

    travel_month = (request.form.get("travel_month") or "").strip() or None
    duration_days_raw = (request.form.get("duration_days") or "").strip() or None
    max_price_raw = (request.form.get("max_price") or "").strip() or None
    currency_code = (request.form.get("currency_code") or "").strip().upper() or None
    non_stop = request.form.get("non_stop") == "on"

    trip_type_raw = (request.form.get("trip_type") or "").strip() or None
    trip_type = TripType(trip_type_raw) if trip_type_raw else None

    # ----- minimal validation -----
    if not origin_tokens:
        trip_types = [t.value for t in TripType]
        return render_template("index.html", trip_types=trip_types, error="Please add at least one origin (e.g., BER).")

    if travel_month and not _MONTH_RE.fullmatch(travel_month):
        trip_types = [t.value for t in TripType]
        return render_template("index.html", trip_types=trip_types, error="Invalid travel month. Use YYYY-MM.")

    duration_days = int(duration_days_raw) if duration_days_raw else None

    # ----- persist Search -----
    search = Search(
        travel_month=travel_month,
        duration_days=duration_days,
        max_price=max_price_raw if max_price_raw else None,
        currency_code=currency_code,
        non_stop=non_stop,
        trip_type=trip_type,
        status="PENDING",
    )
    db.session.add(search)
    db.session.flush()  # populate search.id

    # Phase 1 placeholder: treat origins as airports
    for iata in origin_tokens:
        db.session.add(
            SearchOrigin(
                search_id=search.id,
                iata_code=iata[:3],
                sub_type=OriginSubType.AIRPORT,
            )
        )

    db.session.commit()

    return redirect(url_for("ui.view_search", search_id=search.id))


@ui_bp.get("/searches/<int:search_id>")
def view_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    return render_template("search_results.html", search=search)
