from flask import Flask

from .blueprints.api import api_bp
from .blueprints.ui import ui_bp
from .config import Config
from .extensions import db
from .models import (
    DestinationCandidate,
    OriginSubType,
    Search,
    SearchOrigin,
    SearchOriginStatus,
    TripType,
)
from .services.ai_clients import AnthropicEnricher, OpenAINormalizer
from .services.amadeus_client import AmadeusClient
from .services.rapidapi_skyscanner_client import RapidApiSkyscannerClient


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    register_sqlite_fk_pragma()

    app.travel_data = create_travel_data_provider(app.config)
    app.openai_normalizer = OpenAINormalizer(
        api_base=app.config["OPENAI_API_BASE"],
        api_key=app.config.get("OPENAI_API_KEY") or "",
        model=app.config["OPENAI_MODEL"],
    )
    app.anthropic_enricher = AnthropicEnricher(
        api_base=app.config["ANTHROPIC_API_BASE"],
        api_key=app.config.get("ANTHROPIC_API_KEY") or "",
        model=app.config["ANTHROPIC_MODEL"],
    )

    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    register_cli(app)
    return app


def create_travel_data_provider(config: dict):
    travel_data_provider = (config.get("TRAVEL_DATA_PROVIDER") or "amadeus").lower()
    if travel_data_provider == "amadeus":
        return AmadeusClient(
            base_url=config["AMADEUS_BASE_URL"],
            client_id=config.get("AMADEUS_CLIENT_ID") or "",
            client_secret=config.get("AMADEUS_CLIENT_SECRET") or "",
        )
    if travel_data_provider == "rapidapi_skyscanner":
        return RapidApiSkyscannerClient(
            api_key=config.get("RAPIDAPI_KEY") or "",
            host=config["RAPIDAPI_SKYSCANNER_HOST"],
            market=config["RAPIDAPI_MARKET"],
            locale=config["RAPIDAPI_LOCALE"],
            destination_limit=config["RAPIDAPI_DESTINATION_LIMIT"],
        )
    raise ValueError(f"Unsupported TRAVEL_DATA_PROVIDER: {travel_data_provider}")


def register_sqlite_fk_pragma() -> None:
    """
    Ensure SQLite enforces foreign keys (required for ON DELETE CASCADE).

    SQLite does not enforce foreign key constraints unless PRAGMA foreign_keys=ON
    is enabled for each DB connection, so we set it on connect. [web:489]
    """
    from sqlite3 import Connection as SQLite3Connection

    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, SQLite3Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()


def register_cli(app: Flask) -> None:
    import click
    from flask.cli import with_appcontext

    @app.cli.command("init-db")
    @with_appcontext
    def init_db() -> None:
        """Create all database tables."""
        from . import models  # ensure models are imported before create_all
        db.create_all()       # requires app context
        click.echo("Initialized the database.")

    @app.cli.command("seed-demo")
    @with_appcontext
    def seed_demo() -> None:
        """Seed a small demo search for presentation walkthroughs."""
        db.create_all()

        if Search.query.first():
            click.echo("Database already has data; skipping demo seed.")
            return

        search = Search(
            travel_month="2026-07",
            duration_days=7,
            max_price=850,
            currency_code="EUR",
            non_stop=True,
            trip_type=TripType.CITY_TRIP,
            status="COMPLETED",
        )
        db.session.add(search)
        db.session.flush()

        db.session.add_all(
            [
                SearchOrigin(
                    search_id=search.id,
                    iata_code="BER",
                    sub_type=OriginSubType.AIRPORT,
                    status=SearchOriginStatus.SUCCESS,
                    error_message="Demo data fallback used.",
                ),
                SearchOrigin(
                    search_id=search.id,
                    iata_code="MUC",
                    sub_type=OriginSubType.AIRPORT,
                    status=SearchOriginStatus.SUCCESS,
                    error_message="Demo data fallback used.",
                ),
            ]
        )
        db.session.add_all(
            [
                DestinationCandidate(
                    search_id=search.id,
                    origin_iata="BER",
                    destination_code="LIS",
                    destination_iata="LIS",
                    destination_name="Lisbon",
                    destination_type="CITY",
                    price=189.00,
                    currency_code="EUR",
                    departure_date="2026-07-01",
                    ai_fit_score=82,
                    ai_rationale="Lisbon is a strong city-trip match with warm weather, walkable neighborhoods, and good value.",
                    raw_json='{"source":"seed","destination":"LIS"}',
                ),
                DestinationCandidate(
                    search_id=search.id,
                    origin_iata="MUC",
                    destination_code="LIS",
                    destination_iata="LIS",
                    destination_name="Lisbon",
                    destination_type="CITY",
                    price=219.00,
                    currency_code="EUR",
                    departure_date="2026-07-02",
                    raw_json='{"source":"seed","destination":"LIS"}',
                ),
                DestinationCandidate(
                    search_id=search.id,
                    origin_iata="BER",
                    destination_code="BCN",
                    destination_iata="BCN",
                    destination_name="Barcelona",
                    destination_type="CITY",
                    price=155.00,
                    currency_code="EUR",
                    departure_date="2026-07-05",
                    raw_json='{"source":"seed","destination":"BCN"}',
                ),
            ]
        )
        db.session.commit()
        click.echo(f"Seeded demo search #{search.id}.")
