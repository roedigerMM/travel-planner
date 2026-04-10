from app.extensions import db
from app.models import DestinationCandidate, Search


def test_api_create_search_persists_origin_status_and_candidates(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {},
            },
            {
                "destination_code": "ATH",
                "destination_iata": "ATH",
                "destination_name": "Athens",
                "destination_type": "CITY",
                "price": "180.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-02",
                "raw_json": {},
            },
        ]
    }

    response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "preferences": ["walkable city", "great food"],
            "preference_summary": "Looking for a lively city break with strong food culture.",
        },
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["search"]["status"] == "COMPLETED"
    assert payload["origins"][0]["status"] == "SUCCESS"
    assert len(payload["candidates"]) == 2
    assert payload["candidates"][0]["destination_name"] in {"Lisbon", "Athens"}


def test_api_create_search_handles_origin_failure(client, app):
    app.travel_data.destinations_by_origin = {"BER": RuntimeError("boom")}

    response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "preferences": ["summer city"],
        },
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["search"]["status"] == "ERROR"
    assert payload["origins"][0]["status"] == "ERROR"


def test_api_create_search_normalizes_free_text_to_preferences(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {},
            }
        ]
    }

    response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "free_text": "I want a lively walkable city with great food.",
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["search"]["preference_summary"] == "Looking for a lively city break with food and atmosphere."
    assert [item["label"] for item in payload["search"]["preferences"]] == ["walkable city", "good food"]


def test_api_enrich_updates_candidates(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {},
            }
        ]
    }
    app.anthropic_enricher.responses = {
        "LIS": {"fit_score": 91, "rationale": "Lisbon is a strong city trip with good value and warm summer weather."}
    }
    create_response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "preferences": ["walkable city", "great food"],
            "preference_summary": "Looking for a sunny city with food and atmosphere.",
        },
    )
    search_id = create_response.get_json()["id"]

    response = client.post(f"/api/searches/{search_id}/enrich")

    assert response.status_code == 200
    assert response.get_json()["updated"] is True
    with app.app_context():
        candidate = DestinationCandidate.query.one()
        assert candidate.ai_fit_score == 91


def test_api_enrich_rounds_non_integer_scores(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {},
            }
        ]
    }
    app.anthropic_enricher.responses = {
        "LIS": {"fit_score": 8.5, "rationale": "Rounded score case."}
    }
    create_response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "preferences": ["warm weather"],
        },
    )
    search_id = create_response.get_json()["id"]

    response = client.post(f"/api/searches/{search_id}/enrich")

    assert response.status_code == 200
    with app.app_context():
        candidate = DestinationCandidate.query.one()
        assert candidate.ai_fit_score == 8


def test_api_enrich_requires_preferences(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {},
            }
        ]
    }
    create_response = client.post(
        "/api/searches",
        json={"origins": [{"iata": "BER", "sub_type": "AIRPORT"}]},
    )
    search_id = create_response.get_json()["id"]

    response = client.post(f"/api/searches/{search_id}/enrich")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["updated"] is False
    assert "Preferences are required" in payload["message"]


def test_api_enrich_passes_destination_context_to_anthropic(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {"source": "demo", "origin": "BER", "destination": "LIS"},
            }
        ],
        "MUC": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "240.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-03",
                "raw_json": {"source": "demo", "origin": "MUC", "destination": "LIS"},
            }
        ],
    }
    create_response = client.post(
        "/api/searches",
        json={
            "origins": [
                {"iata": "BER", "sub_type": "AIRPORT"},
                {"iata": "MUC", "sub_type": "AIRPORT"},
            ],
            "preferences": ["walkable city", "good food"],
            "preference_summary": "Looking for a sunny city break with atmosphere.",
        },
    )
    search_id = create_response.get_json()["id"]

    response = client.post(f"/api/searches/{search_id}/enrich")

    assert response.status_code == 200
    assert len(app.anthropic_enricher.calls) == 1
    call = app.anthropic_enricher.calls[0]
    assert call["preferences"] == ["walkable city", "good food"]
    assert call["preference_summary"] == "Looking for a sunny city break with atmosphere."
    assert call["destination_context"]["origin_iatas"] == ["BER", "MUC"]
    assert call["destination_context"]["origin_count"] == 2
    assert call["destination_context"]["min_price"] == 210.0
    assert call["destination_context"]["max_price_seen"] == 240.0


def test_api_create_search_supports_provider_destination_codes_without_iata(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LISB",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "destination_entity_id": "27543833",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {"provider": "rapidapi"},
            }
        ]
    }

    response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "preferences": ["walkable city"],
        },
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["candidates"][0]["destination_code"] == "LISB"
    assert payload["candidates"][0]["destination_name"] == "Lisbon"
    assert payload["candidates"][0]["destination_iata"] == "LISB"


def test_api_preferences_chat_rejects_empty_messages(client):
    response = client.post("/api/preferences/chat", json={"messages": []})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"] == "validation_error"
    assert "No chat input was provided" in payload["message"]


def test_api_locations_suggest_uses_demo_fallback_in_demo_mode(app):
    app.config["TRAVEL_DATA_MODE"] = "demo"
    client = app.test_client()

    response = client.get("/api/locations/suggest?keyword=BER&subTypes=AIRPORT,CITY")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload
    assert any(item["iata"] == "BER" for item in payload)


def test_ui_create_search_persists_origin_provider_metadata(client, app):
    app.travel_data.destinations_by_origin = {
        "BER": [
            {
                "destination_code": "LIS",
                "destination_iata": "LIS",
                "destination_name": "Lisbon",
                "destination_type": "CITY",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {},
            }
        ]
    }

    response = client.post(
        "/searches",
        data={
            "origin_iata": "BER",
            "origin_sub_type": "AIRPORT",
            "origin_provider_sky_id": "BER",
            "origin_provider_entity_id": "95673383",
            "preferences": "walkable city",
        },
        follow_redirects=False,
    )

    assert response.status_code == 302
    with app.app_context():
        search = Search.query.order_by(Search.id.desc()).first()
        assert search is not None
        assert search.origins[0].provider_sky_id == "BER"
        assert search.origins[0].provider_entity_id == "95673383"


def test_homepage_renders_recent_searches(client, app):
    with app.app_context():
        db.session.add(Search(status="COMPLETED"))
        db.session.commit()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Recent Searches" in response.data
    assert b"Search #1" in response.data


def test_seed_demo_command(app):
    runner = app.test_cli_runner()

    result = runner.invoke(args=["seed-demo"])

    assert result.exit_code == 0
    assert "Seeded demo search" in result.output or "skipping demo seed" in result.output.lower()
