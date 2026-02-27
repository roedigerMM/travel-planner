from flask import Flask

from .blueprints.api import api_bp
from .blueprints.ui import ui_bp
from .config import Config
from .extensions import db
from .services.amadeus_client import AmadeusClient


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    db.init_app(app)
    register_sqlite_fk_pragma()

    # Instantiate Amadeus client with config
    app.amadeus = AmadeusClient(
        base_url=app.config["AMADEUS_BASE_URL"],
        client_id=app.config.get("AMADEUS_CLIENT_ID") or "",
        client_secret=app.config.get("AMADEUS_CLIENT_SECRET") or "",
    )

    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    register_cli(app)
    return app


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
