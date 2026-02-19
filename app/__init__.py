from flask import Flask

from .blueprints.ui import ui_bp
from .blueprints.api import api_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # Minimal config for now (we'll expand this in config.py soon)
    app.config["SECRET_KEY"] = "dev"

    # Blueprints
    app.register_blueprint(ui_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
