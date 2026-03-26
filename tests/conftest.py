from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.extensions import db


class DummyAmadeus:
    def __init__(self):
        self.destinations_by_origin = {}
        self.location_results = []

    def search_destinations(self, origin_iata, **kwargs):
        value = self.destinations_by_origin.get(origin_iata, [])
        if isinstance(value, Exception):
            raise value
        return value

    def search_locations(self, keyword, subtypes=None, limit=5):
        return self.location_results[:limit]

    @staticmethod
    def format_error(exc):
        return str(exc)


class DummyAnthropic:
    def __init__(self):
        self.responses = {}

    def enrich_destination(self, destination_iata, **kwargs):
        value = self.responses.get(
            destination_iata,
            {"fit_score": 76, "rationale": f"{destination_iata} is a good fit."},
        )
        if isinstance(value, Exception):
            raise value
        return value


class DummyOpenAI:
    def normalize_search_payload(self, free_text):
        return {
            "origins": [{"iata": "BER", "sub_type": "AIRPORT"}],
            "travel_month": "2026-07",
            "duration_days": 5,
            "max_price": 300,
            "currency_code": "EUR",
            "non_stop": True,
            "trip_type": "CITY_TRIP",
        }


@pytest.fixture
def app(tmp_path):
    db_path = tmp_path / "test.sqlite"
    app = create_app()
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        TRAVEL_DATA_MODE="live",
    )
    app.amadeus = DummyAmadeus()
    app.anthropic_enricher = DummyAnthropic()
    app.openai_normalizer = DummyOpenAI()
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
