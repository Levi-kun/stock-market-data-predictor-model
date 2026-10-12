from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .ticker_store import list_tickers, save_prediction


def run_daily_predictions(app):
    from .dashboard import predict_ticker

    with app.app_context():
        prediction_date = datetime.now(timezone.utc).date()
        try:
            tickers = list_tickers()
        except Exception:
            app.logger.exception("Could not load registered tickers for daily predictions")
            return

        for ticker in tickers:
            try:
                value = predict_ticker(ticker)
                save_prediction(ticker, value, prediction_date)
            except Exception:
                app.logger.exception("Daily prediction failed for %s", ticker)


def start_prediction_scheduler(app):
    if "prediction_scheduler" in app.extensions:
        return

    scheduler = BackgroundScheduler(timezone=timezone.utc)
    scheduler.add_job(
        run_daily_predictions,
        trigger="cron",
        hour=0,
        minute=5,
        args=[app],
        id="daily_ticker_predictions",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.start()
    app.extensions["prediction_scheduler"] = scheduler