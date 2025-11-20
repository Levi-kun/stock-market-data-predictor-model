from flask import current_app, g
import psycopg2


"""

This file handles the initializing of the database connection


"""

# get_db() grabs the database and makes its a globally accesible variable


def get_db():
    if "conn" not in g:
        g.conn = psycopg2.connect(
            database=current_app.config["DB_NAME"],
            host=current_app.config["DB_HOST"],
            port=current_app.config["DB_PORT"],
            user=current_app.config["DB_USER"],
            password=current_app.config["DB_PASSWORD"],
        )

    return g.conn


# this closes the db connection


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# this links the db to the application


def init_app(app):
    app.teardown_appcontext(close_db)


# this is a test


def query_test(sql, params=()):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fethcone()
        return True if row else False
