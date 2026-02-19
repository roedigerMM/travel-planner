# app/__init__.py
from flask import Flask

from .config import Config
from .extensions import db
from .blueprints.ui import ui_bp
from .blueprints.api import api_bp


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    db.init_app(app)

    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    register_cli(app)
    return app


def register_cli(app: Flask) -> None:
    import click
    from flask.cli import with_appcontext

    @app.cli.command("init-db")
    @with_appcontext
    def init_db() -> None:
        """Create all database tables."""
        from . import models  # ensure models are imported before create_all [web:273]
        db.create_all()       # requires app context [web:273]
        click.echo("Initialized the database.")
