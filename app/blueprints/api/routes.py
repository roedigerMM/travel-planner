from flask import jsonify, request, current_app

from . import api_bp
from ...extensions import db
from ...models import Search
from ...services.ai_clients import AIProviderError
from ...services.search_service import (
    ValidationError,
    build_results_payload,
    create_and_execute_search,
    enrich_candidates,
    normalize_payload,
)


@api_bp.get("/health")
def health():
    return jsonify(status="ok")


@api_bp.post("/searches")
def api_create_search():
    data = request.get_json(silent=True) or {}
    try:
        normalized = normalize_payload(data, allow_free_text=True)
        search = create_and_execute_search(normalized)
    except ValidationError as exc:
        return jsonify({"error": "validation_error", "message": str(exc)}), 400
    except AIProviderError as exc:
        return jsonify({"error": "normalization_unavailable", "message": str(exc)}), 503

    return jsonify(
        {
            "id": search.id,
            "redirect_url": f"/searches/{search.id}",
            **build_results_payload(search),
        }
    ), 201


@api_bp.get("/searches/<int:search_id>")
def api_get_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    return jsonify(build_results_payload(search))


@api_bp.patch("/searches/<int:search_id>")
def api_patch_search(search_id: int):
    return jsonify({"error": "not_supported", "message": "Patch is not supported in Phase 1."}), 405


@api_bp.delete("/searches/<int:search_id>")
def api_delete_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    db.session.delete(search)
    db.session.commit()
    return jsonify({"deleted": True, "id": search_id})


@api_bp.get("/searches/<int:search_id>/candidates")
def api_get_candidates(search_id: int):
    search = Search.query.get_or_404(search_id)
    payload = build_results_payload(search)
    return jsonify({"search_id": search.id, "candidates": payload["candidates"]})


@api_bp.get("/locations/suggest")
def api_locations_suggest():
    keyword = (request.args.get("keyword") or "").strip()
    subtypes_raw = (request.args.get("subTypes") or "AIRPORT,CITY").strip()

    if not keyword or len(keyword) < 3:
        return jsonify({"error": "keyword_too_short"}), 400

    subtypes = [s.strip().upper() for s in subtypes_raw.split(",") if s.strip()]

    try:
        items = current_app.amadeus.search_locations(keyword=keyword, subtypes=subtypes, limit=5)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "suggest_unavailable", "message": str(exc)}), 502

    return jsonify(items)


@api_bp.post("/searches/<int:search_id>/enrich")
def api_enrich_search(search_id: int):
    search = Search.query.get_or_404(search_id)
    try:
        result = enrich_candidates(search)
    except AIProviderError as exc:
        return jsonify({"search_id": search.id, "updated": False, "message": str(exc)}), 502

    return jsonify({"search_id": search.id, **result})
