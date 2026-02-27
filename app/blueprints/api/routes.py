from flask import jsonify, request, current_app

from . import api_bp
from ...extensions import db
from ...models import Search, SearchOrigin, TripType, OriginSubType


@api_bp.get("/health")
def health():
    return jsonify(status="ok")


@api_bp.post("/searches")
def api_create_search():
    data = request.get_json(silent=True) or {}  # silent=True => None instead of raising on bad JSON [web:453]

    origins = data.get("origins") or []
    if not origins:
        return jsonify({"error": "origins_required"}), 400  # jsonify + status code tuple is fine [web:471]

    trip_type_raw = data.get("trip_type")
    trip_type = TripType(trip_type_raw) if trip_type_raw else None

    search = Search(
        travel_month=data.get("travel_month"),
        duration_days=data.get("duration_days"),
        max_price=data.get("max_price"),
        currency_code=(data.get("currency_code") or None),
        non_stop=data.get("non_stop"),
        trip_type=trip_type,
        status="PENDING",
    )
    db.session.add(search)
    db.session.flush()  # get search.id

    for o in origins:
        iata = (o.get("iata") or "").upper().strip()
        sub_type_raw = (o.get("sub_type") or "AIRPORT").upper().strip()
        if not iata:
            continue

        db.session.add(
            SearchOrigin(
                search_id=search.id,
                iata_code=iata[:3],
                sub_type=OriginSubType(sub_type_raw),
            )
        )

    db.session.commit()

    return jsonify(
        {
            "id": search.id,
            "redirect_url": f"/searches/{search.id}",
            "search": search.to_dict(include_children=True),
        }
    ), 201  # 201 Created [web:471]


@api_bp.get("/searches/<int:search_id>")
def api_get_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    return jsonify(search.to_dict(include_children=True))  # jsonify returns a proper JSON response [web:443]


@api_bp.patch("/searches/<int:search_id>")
def api_patch_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    data = request.get_json(silent=True) or {}  # silent=True => returns None instead of raising on invalid JSON [web:447][web:453]

    if "travel_month" in data:
        search.travel_month = data["travel_month"] or None

    if "duration_days" in data:
        search.duration_days = data["duration_days"]

    if "max_price" in data:
        search.max_price = data["max_price"]

    if "currency_code" in data:
        cc = (data["currency_code"] or "").strip().upper()
        search.currency_code = cc or None

    if "non_stop" in data:
        search.non_stop = data["non_stop"]

    if "trip_type" in data:
        tt = data["trip_type"]
        search.trip_type = TripType(tt) if tt else None

    if "status" in data:
        search.status = data["status"]

    if "error_message" in data:
        search.error_message = data["error_message"]

    db.session.commit()
    return jsonify(search.to_dict(include_children=True))


@api_bp.delete("/searches/<int:search_id>")
def api_delete_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    db.session.delete(search)
    db.session.commit()
    return jsonify({"deleted": True, "id": search_id})


@api_bp.get("/searches/<int:search_id>/candidates")
def api_get_candidates(search_id: int):
    search = Search.query.get_or_404(search_id)
    return jsonify([c.to_dict() for c in search.candidates])


@api_bp.get("/locations/suggest")
def api_locations_suggest():
    keyword = (request.args.get("keyword") or "").strip()
    subtypes_raw = (request.args.get("subTypes") or "AIRPORT,CITY").strip()

    if not keyword or len(keyword) < 3:
        return jsonify({"error": "keyword_too_short"}), 400

    subtypes = [s.strip().upper() for s in subtypes_raw.split(",") if s.strip()]

    client = current_app.amadeus
    items = client.search_locations(keyword=keyword, subtypes=subtypes, limit=5)

    return jsonify(items)


