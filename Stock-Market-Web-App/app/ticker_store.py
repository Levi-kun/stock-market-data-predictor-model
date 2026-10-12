import math
from datetime import datetime, timedelta, timezone

from .db import get_db


def register_ticker(ticker):
    symbol = ticker.strip().upper()
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO created_tickers (ticker)
                VALUES (%s)
                ON CONFLICT (ticker) DO NOTHING
                """,
                (symbol,),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return symbol


def list_tickers():
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute("SELECT ticker FROM created_tickers ORDER BY ticker")
        return [row[0] for row in cursor.fetchall()]


def save_prediction(ticker, value, prediction_date=None):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Prediction value must be finite.")

    value = max(-1.0, min(1.0, value))
    prediction_date = prediction_date or datetime.now(timezone.utc).date()
    conn = get_db()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO prediction_history (ticker, date, value)
                VALUES (%s, %s, %s)
                ON CONFLICT (ticker, date)
                DO UPDATE SET value = EXCLUDED.value
                """,
                (ticker.strip().upper(), prediction_date, value),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def get_prediction_history(ticker, days=30):
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    conn = get_db()
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT date, value
            FROM prediction_history
            WHERE ticker = %s AND date >= %s
            ORDER BY date
            """,
            (ticker.strip().upper(), cutoff),
        )
        return cursor.fetchall()