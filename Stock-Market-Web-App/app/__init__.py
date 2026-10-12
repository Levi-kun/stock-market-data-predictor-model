import os

from flask import Flask
from .routes import bp
from .auth import get_user_by_id
from .db import init_app as init_db
from .prediction_scheduler import start_prediction_scheduler
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "main.login"  # redirect name


def create_app():
    app = Flask(__name__, template_folder="static/templates", static_folder="static")

    app.config.from_object("config.Config")

    init_db(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(user_id)

    app.register_blueprint(bp)

    @app.before_request
    def start_scheduler():
        is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
        if not app.testing and (not app.debug or is_reloader_child):
            start_prediction_scheduler(app)

    return app
