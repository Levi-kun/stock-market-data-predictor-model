from flask import Flask
from .routes import bp


def create_app():
    app = Flask(__name__, template_folder="static/templates", static_folder="static")

    app.config.from_object("config.Config")

    app.register_blueprint(bp)
    return app
