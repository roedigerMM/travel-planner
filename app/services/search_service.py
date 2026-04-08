import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import current_app
from sqlalchemy.exc import OperationalError

from ..extensions import db
from ..models import (
    DestinationCandidate,
    OriginSubType,
    Search,
    SearchOrigin,
    SearchOriginStatus,
    SearchPreference,
    TripType,
)
from .demo_travel_data import get_demo_destinations

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_IATA_RE = re.compile(r"^[A-Z]{3}$")


class ValidationError(ValueError):
    """Raised when a search payload cannot be normalized safely."""


def normalize_payload(data: dict[str, Any], *, allow_free_text: bool = False) -> dict[str, Any]:
    payload = dict(data or {})
    if allow_free_text and payload.get("free_text"):
        normalized = current_app.openai_normalizer.normalize_search_payload(payload["free_text"])
        payload = {
            **normalized,
            **{k: v for k, v in payload.items() if k != "free_text" and v not in ("", None, [])},
        }

    origins = normalize_origins(payload.get("origins"))
    if not origins:
        raise ValidationError("At least one origin is required.")

    return {
        "origins": origins,
        "travel_month": normalize_travel_month(payload.get("travel_month")),
        "duration_days": normalize_int(payload.get("duration_days"), "Duration"),
        "max_price": normalize_decimal(payload.get("max_price"), "Budget"),
        "currency_code": normalize_currency(payload.get("currency_code")),
        "non_stop": normalize_bool(payload.get("non_stop")),
        "trip_type": normalize_trip_type(payload.get("trip_type")),
        "preferences": normalize_preferences(payload.get("preferences")),
        "preference_summary": normalize_preference_summary(payload.get("preference_summary")),
    }


def normalize_preference_chat_response(payload: dict[str, Any]) -> dict[str, Any]:
    assistant_message = str(payload.get("assistant_message") or "").strip()
    return {
        "assistant_message": assistant_message,
        "preference_summary": normalize_preference_summary(payload.get("preference_summary")),
        "preferences": normalize_preferences(payload.get("preferences")),
    }


def get_recent_searches(limit: int = 5) -> list[Search]:
    try:
        return Search.query.order_by(Search.created_at.desc()).limit(limit).all()
    except OperationalError:
        return []


def create_search_with_origins(normalized: dict[str, Any]) -> Search:
    search = Search(
        travel_month=normalized["travel_month"],
        duration_days=normalized["duration_days"],
        max_price=normalized["max_price"],
        currency_code=normalized["currency_code"],
        non_stop=normalized["non_stop"],
        trip_type=normalized["trip_type"],
        preference_summary=normalized["preference_summary"],
        status="PENDING",
    )
    db.session.add(search)
    db.session.flush()

    for origin in normalized["origins"]:
        db.session.add(
            SearchOrigin(
                search_id=search.id,
                iata_code=origin["iata_code"],
                sub_type=origin["sub_type"],
                status=SearchOriginStatus.PENDING,
            )
        )

    for position, preference in enumerate(normalized["preferences"]):
        db.session.add(
            SearchPreference(
                search_id=search.id,
                label=preference["label"],
                source=preference["source"],
                position=position,
            )
        )

    db.session.commit()
    return search


def create_and_execute_search(normalized: dict[str, Any]) -> Search:
    search = create_search_with_origins(normalized)
    any_success = False
    any_error = False

    for origin in search.origins:
        offers, error_message, used_demo_data = fetch_destination_offers(
            origin_iata=origin.iata_code,
            search=search,
        )

        if error_message and not offers:
            origin.status = SearchOriginStatus.ERROR
            origin.error_message = error_message
            any_error = True
            continue

        if not offers:
            origin.status = SearchOriginStatus.NO_RESULTS
            origin.error_message = "No destination candidates were returned for this origin."
            continue

        origin.status = SearchOriginStatus.SUCCESS
        origin.error_message = "Demo data fallback used." if used_demo_data else None
        any_success = True

        seen_destinations = set()
        for offer in offers:
            destination_iata = offer["destination_iata"]
            if destination_iata in seen_destinations:
                continue
            seen_destinations.add(destination_iata)

            db.session.add(
                DestinationCandidate(
                    search_id=search.id,
                    origin_iata=origin.iata_code,
                    destination_iata=destination_iata,
                    price=offer.get("price"),
                    currency_code=offer.get("currency_code"),
                    departure_date=offer.get("departure_date"),
                    raw_json=json.dumps(offer.get("raw_json") or {}),
                )
            )

    if any_success and any_error:
        search.status = "PARTIAL"
    elif any_success:
        search.status = "COMPLETED"
    elif any_error:
        search.status = "ERROR"
        search.error_message = "All origin lookups failed."
    else:
        search.status = "NO_RESULTS"
        search.error_message = "No destination candidates were found."

    db.session.commit()
    return search


def fetch_destination_offers(origin_iata: str, search: Search) -> tuple[list[dict], str | None, bool]:
    mode = (current_app.config.get("TRAVEL_DATA_MODE") or "auto").lower()

    if mode == "demo":
        return get_demo_destinations(origin_iata), None, True

    try:
        offers = current_app.amadeus.search_destinations(
            origin_iata=origin_iata,
            travel_month=search.travel_month,
            duration_days=search.duration_days,
            max_price=float(search.max_price) if search.max_price is not None else None,
            currency_code=search.currency_code,
            non_stop=search.non_stop,
        )
        return offers, None, False
    except Exception as exc:  # noqa: BLE001
        error_message = current_app.amadeus.format_error(exc)
        if mode == "auto":
            demo_offers = get_demo_destinations(origin_iata)
            if demo_offers:
                return demo_offers, error_message, True
        return [], error_message, False


def aggregate_candidates(candidates: list[DestinationCandidate]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        destination = candidate.destination_iata
        if destination not in merged:
            merged[destination] = {
                "destination_iata": destination,
                "price": float(candidate.price) if candidate.price is not None else None,
                "currency_code": candidate.currency_code,
                "departure_date": candidate.departure_date,
                "origin_iatas": [],
                "origin_count": 0,
                "ai_fit_score": candidate.ai_fit_score,
                "ai_rationale": candidate.ai_rationale,
                "source": "live",
            }

        item = merged[destination]
        item["origin_iatas"].append(candidate.origin_iata)
        item["origin_iatas"] = sorted(set(item["origin_iatas"]))
        item["origin_count"] = len(item["origin_iatas"])

        candidate_price = float(candidate.price) if candidate.price is not None else None
        if item["price"] is None or (candidate_price is not None and candidate_price < item["price"]):
            item["price"] = candidate_price
            item["currency_code"] = candidate.currency_code
            item["departure_date"] = candidate.departure_date

        if candidate.ai_fit_score is not None:
            item["ai_fit_score"] = candidate.ai_fit_score
            item["ai_rationale"] = candidate.ai_rationale

        try:
            raw_payload = json.loads(candidate.raw_json) if candidate.raw_json else {}
        except json.JSONDecodeError:
            raw_payload = {}
        if raw_payload.get("source") == "demo":
            item["source"] = "demo"

    return sorted(
        merged.values(),
        key=lambda item: (
            item["price"] is None,
            item["price"] if item["price"] is not None else 0,
            item["destination_iata"],
        ),
    )


def build_results_payload(search: Search) -> dict[str, Any]:
    return {
        "search": search.to_dict(include_children=True),
        "origins": [origin.to_dict() for origin in search.origins],
        "candidates": aggregate_candidates(search.candidates),
    }


def enrich_candidates(search: Search) -> dict[str, Any]:
    preference_context = get_preference_context(search)
    if not preference_context["preferences"] and not preference_context["preference_summary"]:
        return {
            "updated": False,
            "message": "Preferences are required before AI enrichment can run.",
            "candidates": aggregate_candidates(search.candidates),
        }

    if not search.candidates:
        return {
            "updated": False,
            "message": "Add candidates first before trying AI enrichment.",
            "candidates": [],
        }

    by_destination: dict[str, list[DestinationCandidate]] = defaultdict(list)
    for candidate in search.candidates:
        by_destination[candidate.destination_iata].append(candidate)

    for destination_iata, grouped_candidates in by_destination.items():
        enrichment = current_app.anthropic_enricher.enrich_destination(
            destination_iata=destination_iata,
            preferences=preference_context["preferences"],
            preference_summary=preference_context["preference_summary"],
            travel_month=search.travel_month,
            duration_days=search.duration_days,
            max_price=float(search.max_price) if search.max_price is not None else None,
            currency_code=search.currency_code,
        )
        score = normalize_fit_score(enrichment.get("fit_score"))
        rationale = (enrichment.get("rationale") or "").strip() or None
        for candidate in grouped_candidates:
            candidate.ai_fit_score = score
            candidate.ai_rationale = rationale

    db.session.commit()
    return {
        "updated": True,
        "message": "AI enrichment completed.",
        "candidates": aggregate_candidates(search.candidates),
    }


def get_preference_context(search: Search) -> dict[str, Any]:
    preferences = [preference.label for preference in search.preferences if preference.label]
    summary = (search.preference_summary or "").strip() or None

    if not preferences and search.trip_type:
        preferences = [search.trip_type.value.replace("_", " ").lower()]

    return {
        "preferences": preferences,
        "preference_summary": summary,
    }


def normalize_origins(origins: Any) -> list[dict[str, Any]]:
    if origins is None:
        return []

    normalized = []
    if isinstance(origins, str):
        tokens = [token.strip().upper() for token in origins.split(",") if token.strip()]
        origins = [{"iata": token, "sub_type": "AIRPORT"} for token in tokens]

    for raw_origin in origins:
        if not isinstance(raw_origin, dict):
            raise ValidationError("Origins must be objects with iata and sub_type.")
        iata = (raw_origin.get("iata") or raw_origin.get("iata_code") or "").strip().upper()
        if not _IATA_RE.fullmatch(iata):
            raise ValidationError(f"Invalid origin code: {iata or 'blank'}.")
        sub_type_raw = (raw_origin.get("sub_type") or "AIRPORT").strip().upper()
        try:
            sub_type = OriginSubType(sub_type_raw)
        except ValueError as exc:
            raise ValidationError(f"Invalid origin sub-type: {sub_type_raw}.") from exc
        normalized.append({"iata_code": iata, "sub_type": sub_type})
    return normalized


def normalize_travel_month(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not _MONTH_RE.fullmatch(text):
        raise ValidationError("Travel month must use YYYY-MM format.")
    return text


def normalize_int(value: Any, label: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{label} must be an integer.") from exc
    if parsed <= 0:
        raise ValidationError(f"{label} must be greater than zero.")
    return parsed


def normalize_decimal(value: Any, label: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValidationError(f"{label} must be a valid number.") from exc
    if parsed < 0:
        raise ValidationError(f"{label} cannot be negative.")
    return parsed


def normalize_currency(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip().upper()
    if len(text) != 3 or not text.isalpha():
        raise ValidationError("Currency code must be a 3-letter code.")
    return text


def normalize_trip_type(value: Any) -> TripType | None:
    if value in (None, ""):
        return None
    try:
        return TripType(str(value).strip())
    except ValueError as exc:
        raise ValidationError(f"Invalid trip type: {value}.") from exc


def normalize_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    raise ValidationError("Non-stop must be a boolean value.")


def normalize_fit_score(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0
    score = round(score)
    return max(0, min(100, int(score)))


def normalize_preferences(value: Any) -> list[dict[str, str]]:
    if value in (None, ""):
        return []

    items = []
    if isinstance(value, str):
        tokens = [token.strip() for token in value.split(",") if token.strip()]
        value = [{"label": token, "source": "USER"} for token in tokens]

    for item in value:
        if isinstance(item, str):
            label = item.strip()
            source = "USER"
        elif isinstance(item, dict):
            label = str(item.get("label") or "").strip()
            source = str(item.get("source") or "USER").strip().upper()
        else:
            raise ValidationError("Preferences must be strings or objects with label/source.")

        if not label:
            continue
        items.append({"label": label[:80], "source": source[:20] or "USER"})

    deduped = []
    seen = set()
    for item in items:
        key = item["label"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def normalize_preference_summary(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text[:500] if text else None
