# app/users.py
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db


# -----------------------------
# User object for Flask-Login
# -----------------------------
class UserObj:
    """Lightweight object for Flask-Login."""

    def __init__(self, id, username, email, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash

    def get_id(self):
        return str(self.id)

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# -----------------------------
# User creation & management
# -----------------------------
def create_user(username, email, password):
    """
    Creates a new user.
    Returns (UserObj, None) if successful, (None, error_msg) if failed.
    """
    if user_exists(username=username):
        return None, "A user with that username already exists."
    if user_exists(email=email):
        return None, "A user with that email already exists."

    hashed = generate_password_hash(password)
    user_id = insert_user(username, email, hashed)
    if not user_id:
        return None, "Error creating your account."

    return get_user_by_id(user_id), None


def user_exists(username=None, email=None):
    """
    Check if a user exists by username or email.
    """
    sql = "SELECT id FROM users WHERE "
    params = ()
    if username:
        sql += "username = %s LIMIT 1"
        params = (username,)
    elif email:
        sql += "email = %s LIMIT 1"
        params = (email,)
    else:
        return False

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone() is not None


def insert_user(username, email, password_hash):
    """
    Insert a user into the database.
    Returns the user ID on success, None on failure.
    """
    sql = """
        INSERT INTO users (username, email, password_hash)
        VALUES (%s, %s, %s)
        RETURNING id
    """
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (username, email, password_hash))
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id
    except Exception as e:
        print("Insert user error:", e)
        conn.rollback()
        return None


# -----------------------------
# User retrieval
# -----------------------------
def get_user_by_email(email):
    return _get_user("email", email)


def get_user_by_username(username):
    return _get_user("username", username)


def get_user_by_id(user_id):
    return _get_user("id", user_id)


def _get_user(field, value):
    """
    Internal function to fetch a user by any field.
    """
    sql = f"SELECT id, username, email, password_hash FROM users WHERE {field} = %s LIMIT 1"
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, (value,))
        row = cur.fetchone()
        if row:
            return UserObj(*row)
        return None
