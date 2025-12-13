from flask import request, redirect, url_for, flash
from flask_login import login_user
from .auth import get_user_by_email  # or get_user_by_username


def handle_login():
    email = request.form.get("email")  # matches input field name
    password = request.form.get("password")
    remember = request.form.get("remember") == "on"

    # Validate input
    if not email or not password:
        flash("Please enter both email and password.", "error")
        return redirect(url_for("main.login"))  # update to your login route endpoint

    # Fetch user from DB
    user = get_user_by_email(email)  # could also use username if login is via username

    # Authenticate
    if user is None or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("main.login"))

    # Log the user in
    login_user(user, remember=remember)
    flash(f"Welcome back, {user.username}!", "success")
    return redirect(url_for("main.dashboard"))  # update to your main page endpoint
