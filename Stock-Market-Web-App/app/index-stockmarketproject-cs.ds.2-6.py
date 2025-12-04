from flask import Blueprint, render_template, request
from .dashboard import handle_dashboard
from .db import query_test
from .feedback import handle_feedback
from .login import handle_login
from .register import handle_registration
import plotly.express as px
import pandas as pd

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if request.method == "POST":
        return handle_dashboard()

    days = [1, 2, 3, 4, 5]
    prices = [120, 135, 128, 142, 150]
    amount = [1000, 1000, 900, 900, 850]

    df = pd.DataFrame({"Day": days, "Price": prices, "Stock Amount": amount})

    fig1 = px.line(df, x="Day", y=["Price", "Stock Amount"], title="Stock Over Price")

    fig2 = px.pie(
        names=["Feature A", "Feature B", "Feature C"],
        values=[50, 30, 20],
        title="Feature 1 vs Stock Amount",
    )

    fig3 = px.bar(
        x=["Good", "Neutral", "Bad"],
        y=[60, 25, 15],
        title="Sentiment over Stock Amount",
    )

    graph1 = fig1.to_html(full_html=False)
    graph2 = fig2.to_html(full_html=False)
    graph3 = fig3.to_html(full_html=False)

    return render_template(
        "dashboard.html",
        active="dashboard",
        graph1=graph1,
        graph2=graph2,
        graph3=graph3,
    )

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return handle_login()
    return render_template("login.html", active="login")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        handle_registration()
    return render_template("register.html", active="login")


@bp.route("/about")
def about():
    return render_template("about.html", active="about")


@bp.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        return handle_feedback()
    return render_template("feedback.html", active="feedback")
