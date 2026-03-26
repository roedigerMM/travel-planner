from flask import render_template, request, redirect, url_for

from . import ui_bp
from ...models import Search, TripType
from ...services.search_service import (
    ValidationError,
    build_results_payload,
    create_and_execute_search,
    normalize_payload,
)


@ui_bp.get("/")
def index():
    trip_types = [t.value for t in TripType]
    return render_template("index.html", trip_types=trip_types, error=None)


@ui_bp.post("/searches")
def create_search():
    payload = {
        "origins": request.form.get("origins") or "",
        "travel_month": request.form.get("travel_month") or None,
        "duration_days": request.form.get("duration_days") or None,
        "max_price": request.form.get("max_price") or None,
        "currency_code": request.form.get("currency_code") or None,
        "non_stop": request.form.get("non_stop"),
        "trip_type": request.form.get("trip_type") or None,
    }
    try:
        normalized = normalize_payload(payload)
        search = create_and_execute_search(normalized)
    except ValidationError as exc:
        trip_types = [t.value for t in TripType]
        return render_template("index.html", trip_types=trip_types, error=str(exc)), 400

    return redirect(url_for("ui.view_search", search_id=search.id))


@ui_bp.get("/searches/<int:search_id>")
def view_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    payload = build_results_payload(search)
    return render_template(
        "search_results.html",
        search=search,
        origins=payload["origins"],
        candidates=payload["candidates"],
    )
