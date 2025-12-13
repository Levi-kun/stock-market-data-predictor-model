from flask import request, redirect, url_for, flash
from flask_login import login_user
from .auth import create_user


def handle_registration():
    username = request.form.get("username")
    email = request.form.get("email")
    password = request.form.get("password")

    user, error = create_user(username, email, password)

    if error:  # only redirect if there truly is an error
        print("DEBUG:", user, error)

        flash(error, "error")
        return redirect(url_for("main.register"))

    flash("Account created successfully!", "success")
    return redirect(url_for("main.login"))
