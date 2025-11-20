"""
This routes.py script will contain the routes/path for our application
"""

from flask import Blueprint, render_template, request
from .db import query_test
from .login import handle_login
from .register import handle_registration

bp = Blueprint("main", __name__)


## initializes a blue print
@bp.route("/")
def index():
    ## we will change this to render html home page later on
    # ok = query_test("SELECT 1")
    # if ok:
    #    return "<h1> Flask is running! Database Connection is Suceessful! </h1>"
    # else:
    #    return "<h1> Flask is running! BUT Datavse test query returned no results! :c </h1>"
    return render_template("index.html")


## add the route for the login
@bp.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        return 1
    return render_template("dashboard.html")


@bp.route("/login", methods=["GET", "POST"])  ## local host / login
def login():
    if request.method == "POST":
        return handle_login()  # the backend for the /login reciever is in app/login.py
    return render_template("login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        handle_registration()  # the backend for the /register POST event is in app/register.py
    return render_template("register.html")


@bp.route("/about")
def about():
    return render_template("about.html")


@bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        return 0
    return render_template("feedback.html")
