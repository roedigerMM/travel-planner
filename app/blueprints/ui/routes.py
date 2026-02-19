from flask import render_template

from . import ui_bp


@ui_bp.get("/")
def index():
    return render_template("index.html")
