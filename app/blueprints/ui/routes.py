from flask import render_template, request, redirect, url_for

from . import ui_bp
from ...models import Search
from ...services.search_service import (
    ValidationError,
    build_results_payload,
    create_and_execute_search,
    get_recent_searches,
    normalize_payload,
)


@ui_bp.get("/")
def index():
    return render_template(
        "index.html",
        recent_searches=get_recent_searches(),
        error=None,
        form_data=default_form_data(),
    )


@ui_bp.post("/searches")
def create_search():
    payload = {
        "origins": form_origins_from_request(),
        "travel_month": request.form.get("travel_month") or None,
        "duration_days": request.form.get("duration_days") or None,
        "max_price": request.form.get("max_price") or None,
        "currency_code": request.form.get("currency_code") or None,
        "non_stop": request.form.get("non_stop"),
        "trip_type": request.form.get("trip_type") or None,
        "preferences": request.form.get("preferences") or None,
        "preference_summary": request.form.get("preference_summary") or None,
    }
    try:
        normalized = normalize_payload(payload)
        search = create_and_execute_search(normalized)
    except ValidationError as exc:
        form_data = default_form_data()
        form_data.update(
            {
                "travel_month": payload["travel_month"] or "",
                "duration_days": payload["duration_days"] or "",
                "max_price": payload["max_price"] or "",
                "currency_code": payload["currency_code"] or "EUR",
                "non_stop": payload["non_stop"] in ("on", True, "true", "1"),
                "trip_type": payload["trip_type"] or "",
                "preferences": payload["preferences"] or "",
                "preference_summary": payload["preference_summary"] or "",
                "origins_manual": request.form.get("origins_manual") or "",
                "origins": payload["origins"] if isinstance(payload["origins"], list) else [],
            }
        )
        return render_template(
            "index.html",
            recent_searches=get_recent_searches(),
            error=str(exc),
            form_data=form_data,
        ), 400

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


def form_origins_from_request():
    iatas = request.form.getlist("origin_iata")
    sub_types = request.form.getlist("origin_sub_type")
    provider_sky_ids = request.form.getlist("origin_provider_sky_id")
    provider_entity_ids = request.form.getlist("origin_provider_entity_id")
    selected = []
    for index, iata in enumerate(iatas):
        code = (iata or "").strip()
        if not code:
            continue
        selected.append(
            {
                "iata": code,
                "sub_type": sub_types[index] if index < len(sub_types) else "AIRPORT",
                "provider_sky_id": provider_sky_ids[index] if index < len(provider_sky_ids) else "",
                "provider_entity_id": provider_entity_ids[index] if index < len(provider_entity_ids) else "",
            }
        )
    if selected:
        return selected
    return request.form.get("origins_manual") or request.form.get("origins") or ""


def default_form_data():
    return {
        "origins": [],
        "origins_manual": "",
        "travel_month": "",
        "duration_days": "",
        "max_price": "",
        "currency_code": "EUR",
        "non_stop": False,
        "trip_type": "",
        "preferences": "",
        "preference_summary": "",
    }
