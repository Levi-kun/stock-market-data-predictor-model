from .db import get_db


def insert_feedback(name, major, email, feedback):
    cur = """
                     INSERT INTO feedback (name, major, email, feedback)
                     VALUES (%s, %s, %s, %s)
                     """
    return safe_insert(cur, (name, major, email, feedback))


def safe_insert(sql, params=()):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        return False, str(e)


def handle_feedback(name, major, email, feedback):
    success = insert_feedback(name, major, email, feedback)
    return success
