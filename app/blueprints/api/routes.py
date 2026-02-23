from flask import jsonify, request

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

