from app.extensions import db
from app.models import DestinationCandidate, Search


def test_api_create_search_persists_origin_status_and_candidates(client, app):
    app.amadeus.destinations_by_origin = {
        "BER": [
            {
                "destination_iata": "LIS",
                "price": "210.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-01",
                "raw_json": {},
            },
            {
                "destination_iata": "ATH",
                "price": "180.00",
                "currency_code": "EUR",
                "departure_date": "2026-07-02",
                "raw_json": {},
            },
        ]
    }

    response = client.post(
        "/api/searches",
        json={"origins": [{"iata": "BER", "sub_type": "AIRPORT"}], "trip_type": "CITY_TRIP"},
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["search"]["status"] == "COMPLETED"
    assert payload["origins"][0]["status"] == "SUCCESS"
    assert len(payload["candidates"]) == 2


def test_api_create_search_handles_origin_failure(client, app):
    app.amadeus.destinations_by_origin = {"BER": RuntimeError("boom")}

    response = client.post(
        "/api/searches",
        json={"origins": [{"iata": "BER", "sub_type": "AIRPORT"}], "trip_type": "CITY_TRIP"},
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert payload["search"]["status"] == "ERROR"
    assert payload["origins"][0]["status"] == "ERROR"


def test_api_enrich_updates_candidates(client, app):
    app.amadeus.destinations_by_origin = {
        "BER": [
            {
                "destination_iata": "LIS",
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
        json={"origins": [{"iata": "BER", "sub_type": "AIRPORT"}], "trip_type": "CITY_TRIP"},
    )
    search_id = create_response.get_json()["id"]

    response = client.post(f"/api/searches/{search_id}/enrich")

    assert response.status_code == 200
    assert response.get_json()["updated"] is True
    with app.app_context():
        candidate = DestinationCandidate.query.one()
        assert candidate.ai_fit_score == 91


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
