from flask import render_template, flash, redirect, url_for
from flask_login import current_user
from app import db
from app.models import User
from app.auth.forms import RegistrationForm

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('You are now a registered user!')
        return redirect('/login')
    return render_template('register.html', title='Register')
