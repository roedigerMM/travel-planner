from unittest.mock import Mock, patch

from app import create_app
from app.extensions import db
from app.models import DestinationCandidate, Search
from app.services.rapidapi_skyscanner_client import RapidApiSkyscannerClient


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


def test_api_candidates_hide_items_without_departure_date(client, app):
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
                "destination_code": "MAD",
                "destination_iata": "MAD",
                "destination_name": "Madrid",
                "destination_type": "CITY",
                "price": "120.00",
                "currency_code": "EUR",
                "departure_date": None,
                "raw_json": {},
            },
        ]
    }

    response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "preferences": ["walkable city"],
        },
    )

    payload = response.get_json()
    assert response.status_code == 201
    assert [item["destination_code"] for item in payload["candidates"]] == ["LIS"]
    assert payload["candidates"][0]["departure_date"] == "2026-07-01"


def test_api_candidates_sort_by_fit_score_descending_after_enrichment(client, app):
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
    app.anthropic_enricher.responses = {
        "LIS": {"fit_score": 72, "rationale": "Good option."},
        "ATH": {"fit_score": 94, "rationale": "Best match."},
    }
    create_response = client.post(
        "/api/searches",
        json={
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "preferences": ["warm weather", "good food"],
        },
    )
    search_id = create_response.get_json()["id"]

    response = client.post(f"/api/searches/{search_id}/enrich")

    payload = response.get_json()
    assert response.status_code == 200
    assert [item["destination_code"] for item in payload["candidates"]] == ["ATH", "LIS"]
    assert [item["ai_fit_score"] for item in payload["candidates"]] == [94, 72]


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


def test_create_app_supports_rapidapi_skyscanner_provider(tmp_path):
    db_path = tmp_path / "test-rapidapi.sqlite"
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "TRAVEL_DATA_PROVIDER": "rapidapi_skyscanner",
            "RAPIDAPI_KEY": "test-key",
            "RAPIDAPI_SKYSCANNER_HOST": "skyscanner-flights-travel-api.p.rapidapi.com",
            "RAPIDAPI_MARKET": "DE",
            "RAPIDAPI_LOCALE": "de-DE",
            "RAPIDAPI_DESTINATION_LIMIT": 10,
        }
    )

    assert isinstance(app.travel_data, RapidApiSkyscannerClient)


def test_rapidapi_skyscanner_search_locations_normalizes_places():
    client = RapidApiSkyscannerClient(
        api_key="test-key",
        host="skyscanner-flights-travel-api.p.rapidapi.com",
        market="DE",
        locale="de-DE",
    )
    response = Mock()
    response.json.return_value = {
        "places": [
            {
                "skyId": "LOND",
                "entityId": "27544008",
                "iataCode": "LON",
                "name": "London",
                "cityName": "London",
                "countryName": "United Kingdom",
                "placeType": "CITY",
            },
            {
                "skyId": "LHR",
                "entityId": "95565050",
                "iataCode": "",
                "name": "London Heathrow",
                "cityName": "London",
                "countryName": "United Kingdom",
                "placeType": "AIRPORT",
            },
        ]
    }
    response.raise_for_status.return_value = None

    with patch("app.services.rapidapi_skyscanner_client.requests.get", return_value=response):
        items = client.search_locations("London", subtypes=["CITY", "AIRPORT"], limit=5)

    assert items == [
        {
            "sub_type": "CITY",
            "name": "London",
            "iata": "LON",
            "city_name": "London",
            "city_code": "LON",
            "country_code": None,
            "provider_sky_id": "LOND",
            "provider_entity_id": "27544008",
        },
        {
            "sub_type": "AIRPORT",
            "name": "London Heathrow",
            "iata": "LHR",
            "city_name": "London",
            "city_code": None,
            "country_code": None,
            "provider_sky_id": "LHR",
            "provider_entity_id": "95565050",
        },
    ]


def test_rapidapi_skyscanner_search_destinations_normalizes_everywhere_results():
    client = RapidApiSkyscannerClient(
        api_key="test-key",
        host="skyscanner-flights-travel-api.p.rapidapi.com",
        market="DE",
        locale="de-DE",
    )
    response = Mock()
    response.json.return_value = {
        "destinations": [
            {
                "skyId": "LISB",
                "entityId": "27543833",
                "name": "Lisbon",
                "countryName": "Portugal",
                "price": 16.99,
                "currency": "GBP",
                "isDirect": True,
                "imageUrl": "",
            },
            {
                "skyId": "ROME",
                "entityId": "27536545",
                "name": "Rome",
                "countryName": "Italy",
                "price": "13.97",
                "currency": "GBP",
                "isDirect": True,
                "imageUrl": "",
            },
        ]
    }
    response.raise_for_status.return_value = None

    with patch("app.services.rapidapi_skyscanner_client.requests.get", return_value=response):
        items = client.search_destinations(
            origin_iata="LON",
            origin_sky_id="LOND",
            origin_entity_id="27544008",
            currency_code="EUR",
        )

    assert items == [
        {
            "destination_code": "LISB",
            "destination_iata": None,
            "destination_entity_id": "27543833",
            "destination_name": "Lisbon",
            "destination_type": "CITY",
            "price": 16.99,
            "currency_code": "GBP",
            "departure_date": None,
            "raw_json": {
                "skyId": "LISB",
                "entityId": "27543833",
                "name": "Lisbon",
                "countryName": "Portugal",
                "price": 16.99,
                "currency": "GBP",
                "isDirect": True,
                "imageUrl": "",
            },
        },
        {
            "destination_code": "ROME",
            "destination_iata": None,
            "destination_entity_id": "27536545",
            "destination_name": "Rome",
            "destination_type": "CITY",
            "price": 13.97,
            "currency_code": "GBP",
            "departure_date": None,
            "raw_json": {
                "skyId": "ROME",
                "entityId": "27536545",
                "name": "Rome",
                "countryName": "Italy",
                "price": "13.97",
                "currency": "GBP",
                "isDirect": True,
                "imageUrl": "",
            },
        },
    ]


def test_rapidapi_skyscanner_search_destinations_resolves_monthly_cheapest_price():
    client = RapidApiSkyscannerClient(
        api_key="test-key",
        host="skyscanner-flights-travel-api.p.rapidapi.com",
        market="DE",
        locale="de-DE",
    )
    everywhere_response = Mock()
    everywhere_response.json.return_value = {
        "destinations": [
            {
                "skyId": "LISB",
                "entityId": "27543833",
                "name": "Lisbon",
                "countryName": "Portugal",
                "price": 16.99,
                "currency": "GBP",
                "isDirect": True,
                "imageUrl": "",
            }
        ]
    }
    everywhere_response.raise_for_status.return_value = None

    cheapest_response = Mock()
    cheapest_response.json.return_value = {
        "cheapest": [
            {"date": "2026-06-29", "price": 99.0, "currency": "EUR"},
            {"date": "2026-07-03", "price": 149.0},
            {"date": "2026-07-01", "price": 129.0},
            {"date": "2026-08-01", "price": 79.0, "currency": "EUR"},
        ],
    }
    cheapest_response.raise_for_status.return_value = None

    with patch(
        "app.services.rapidapi_skyscanner_client.requests.get",
        side_effect=[everywhere_response, cheapest_response],
    ):
        items = client.search_destinations(
            origin_iata="LON",
            origin_sky_id="LOND",
            origin_entity_id="27544008",
            travel_month="2026-07",
            currency_code="EUR",
        )

    assert items[0]["price"] == 129.0
    assert items[0]["departure_date"] == "2026-07-01"
    assert items[0]["currency_code"] == "EUR"


def test_rapidapi_skyscanner_search_destinations_ignores_cheapest_days_outside_requested_month():
    client = RapidApiSkyscannerClient(
        api_key="test-key",
        host="skyscanner-flights-travel-api.p.rapidapi.com",
        market="DE",
        locale="de-DE",
    )
    everywhere_response = Mock()
    everywhere_response.json.return_value = {
        "destinations": [
            {
                "skyId": "PARI",
                "entityId": "27539733",
                "name": "Paris",
                "countryName": "France",
                "price": 49.0,
                "currency": "EUR",
                "isDirect": True,
                "imageUrl": "",
            }
        ]
    }
    everywhere_response.raise_for_status.return_value = None

    cheapest_response = Mock()
    cheapest_response.json.return_value = {
        "cheapest": [
            {"date": "2026-06-28", "price": 10.0, "currency": "EUR"},
            {"date": "2026-08-02", "price": 12.0, "currency": "EUR"},
        ],
    }
    cheapest_response.raise_for_status.return_value = None

    with patch(
        "app.services.rapidapi_skyscanner_client.requests.get",
        side_effect=[everywhere_response, cheapest_response],
    ):
        items = client.search_destinations(
            origin_iata="BER",
            origin_sky_id="BER",
            origin_entity_id="95673383",
            travel_month="2026-07",
            currency_code="EUR",
        )

    assert items[0]["price"] == 49.0
    assert items[0]["departure_date"] is None
    assert items[0]["currency_code"] == "EUR"


def test_rapidapi_skyscanner_search_destinations_keeps_preview_price_if_month_lookup_fails():
    client = RapidApiSkyscannerClient(
        api_key="test-key",
        host="skyscanner-flights-travel-api.p.rapidapi.com",
        market="DE",
        locale="de-DE",
    )
    everywhere_response = Mock()
    everywhere_response.json.return_value = {
        "destinations": [
            {
                "skyId": "ROME",
                "entityId": "27536545",
                "name": "Rome",
                "countryName": "Italy",
                "price": 13.97,
                "currency": "GBP",
                "isDirect": True,
                "imageUrl": "",
            }
        ]
    }
    everywhere_response.raise_for_status.return_value = None

    with patch(
        "app.services.rapidapi_skyscanner_client.requests.get",
        side_effect=[everywhere_response, RuntimeError("month lookup failed")],
    ):
        items = client.search_destinations(
            origin_iata="LON",
            origin_sky_id="LOND",
            origin_entity_id="27544008",
            travel_month="2026-07",
            currency_code="EUR",
        )

    assert items[0]["price"] == 13.97
    assert items[0]["departure_date"] is None
    assert items[0]["currency_code"] == "GBP"


def test_rapidapi_skyscanner_search_destinations_limits_monthly_price_lookups():
    client = RapidApiSkyscannerClient(
        api_key="test-key",
        host="skyscanner-flights-travel-api.p.rapidapi.com",
        market="DE",
        locale="de-DE",
        destination_limit=2,
    )
    everywhere_response = Mock()
    everywhere_response.json.return_value = {
        "destinations": [
            {"skyId": "LISB", "entityId": "1", "name": "Lisbon", "price": 100, "currency": "EUR"},
            {"skyId": "ROME", "entityId": "2", "name": "Rome", "price": 110, "currency": "EUR"},
            {"skyId": "PARI", "entityId": "3", "name": "Paris", "price": 120, "currency": "EUR"},
        ]
    }
    everywhere_response.raise_for_status.return_value = None

    cheapest_lisbon_response = Mock()
    cheapest_lisbon_response.json.return_value = {
        "cheapest": [{"date": "2026-07-01", "price": 90, "currency": "EUR"}]
    }
    cheapest_lisbon_response.raise_for_status.return_value = None

    cheapest_rome_response = Mock()
    cheapest_rome_response.json.return_value = {
        "cheapest": [{"date": "2026-07-02", "price": 95, "currency": "EUR"}]
    }
    cheapest_rome_response.raise_for_status.return_value = None

    with patch(
        "app.services.rapidapi_skyscanner_client.requests.get",
        side_effect=[everywhere_response, cheapest_lisbon_response, cheapest_rome_response],
    ) as mock_get:
        items = client.search_destinations(
            origin_iata="LON",
            origin_sky_id="LOND",
            origin_entity_id="27544008",
            travel_month="2026-07",
            currency_code="EUR",
        )

    assert [item["destination_code"] for item in items] == ["LISB", "ROME"]
    assert mock_get.call_count == 3


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
