import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


ROOT_DIR = Path(__file__).resolve().parent
YAHOO_DATA_DIR = ROOT_DIR / "datasets_yahoo"
YAHOO_TICKERS = (
    "AAPL", "AMD", "AMZN", "BA", "COST", "CSCO", "DIS", "GE", "INTC",
    "JPM", "KO", "META", "MSFT", "NFLX", "NVDA", "PFE", "TSLA", "TSM",
    "UNH", "V", "WMT", "XOM",
)
PRICE_FEATURE_COLS = [
    "momentum_3m",
    "momentum_12m",
    "volatility_90d",
    "volume_trend_90d",
]
ANALYST_FEATURE_COLS = [
    "analyst_rating_mean_1y",
    "analyst_buy_share_1y",
    "analyst_downgrade_share_1y",
    "analyst_action_count_1y",
    "analyst_target_upside_1y",
    "analyst_target_revision_1y",
]
EARNINGS_FEATURE_COLS = [
    "earnings_surprise_mean_1y",
    "earnings_beat_rate_1y",
    "earnings_surprise_count_1y",
    "next_quarter_eps_estimate",
    "next_quarter_eps_change",
]
FEATURE_COLS = [
    "log_cap",
    "log_revenue",
    "earnings_yield",
    "revenue_yield",
    "fcf_yield",
    "ocf_yield",
    "debt_assets",
    "issuance_yield",
    "repurchase_yield",
    "sbc_revenue",
    "earnings_growth",
    "revenue_growth",
    "eps_growth",
    "log_assets",
    "log_debt",
    "signed_log_income",
    "signed_log_issuance",
    *PRICE_FEATURE_COLS,
    *ANALYST_FEATURE_COLS,
    *EARNINGS_FEATURE_COLS,
    "undervaluation_beat_signal",
]
SHORTAGE_PATTERN = re.compile(
    r"\b(shortage|shortages|supply chain|supply constraint|component constraint|"
    r"backlog|inventory constraint|capacity constraint)\b",
    re.IGNORECASE,
)
SENTIMENT_ANALYZER = SentimentIntensityAnalyzer()


def yahoo_ticker_universe():
    screened = []
    query = yf.EquityQuery(
        "and",
        [
            yf.EquityQuery("eq", ["region", "us"]),
            yf.EquityQuery("gt", ["intradaymarketcap", 2_000_000_000]),
            yf.EquityQuery("is-in", ["exchange", "NMS", "NYQ"]),
        ],
    )
    for offset in (0, 250):
        quotes = yf.screen(
            query,
            offset=offset,
            size=250,
            sortField="intradaymarketcap",
            sortAsc=False,
        ).get("quotes", [])
        for quote in quotes:
            symbol = quote.get("symbol")
            if (
                quote.get("quoteType") != "EQUITY"
                or quote.get("currency") != "USD"
                or not symbol
                or symbol == "GOOG"
                or ("-" in symbol and symbol != "BRK-B")
            ):
                continue
            screened.append(symbol)

    return tuple(dict.fromkeys([*YAHOO_TICKERS, *screened]))


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return np.nan
    return result if np.isfinite(result) else np.nan


def _price_behavior_features(prices, as_of):
    features = {column: np.nan for column in PRICE_FEATURE_COLS}
    if prices.empty:
        return features

    prices = prices.copy()
    price_index = pd.DatetimeIndex(prices.index)
    if price_index.tz is not None:
        price_index = price_index.tz_localize(None)
    prices.index = price_index
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    prices = prices.loc[prices.index <= cutoff]
    if prices.empty:
        return features

    close_column = "Adj Close" if "Adj Close" in prices.columns else "Close"
    close = pd.to_numeric(prices[close_column], errors="coerce").dropna()
    if len(close) >= 64:
        features["momentum_3m"] = close.iloc[-1] / close.iloc[-64] - 1
        returns = close.pct_change().dropna().tail(63)
        features["volatility_90d"] = returns.std(ddof=0) * np.sqrt(252)
    if len(close) >= 253:
        features["momentum_12m"] = close.iloc[-1] / close.iloc[-253] - 1

    if "Volume" in prices.columns:
        volume = pd.to_numeric(prices["Volume"], errors="coerce").dropna()
        if len(volume) >= 126:
            prior_volume = volume.iloc[-126:-63].mean()
            recent_volume = volume.iloc[-63:].mean()
            if prior_volume > 0:
                features["volume_trend_90d"] = recent_volume / prior_volume - 1
    return features


def _naive_datetime_index(index):
    dates = pd.DatetimeIndex(pd.to_datetime(index, errors="coerce"))
    return dates.tz_localize(None) if dates.tz is not None else dates


def _rating_score(grade):
    grade = re.sub(r"[^a-z]", "", str(grade).lower())
    if "strongsell" in grade:
        return 5.0
    if "sell" in grade or "underperform" in grade or "underweight" in grade or "reduce" in grade:
        return 4.0
    if "strongbuy" in grade:
        return 1.0
    if "buy" in grade or "outperform" in grade or "overweight" in grade:
        return 2.0
    if "hold" in grade or "neutral" in grade or "marketperform" in grade or "equalweight" in grade:
        return 3.0
    return np.nan


def _analyst_history_features(history, as_of, price):
    features = {column: np.nan for column in ANALYST_FEATURE_COLS}
    if not isinstance(history, pd.DataFrame) or history.empty:
        return features

    history = history.copy()
    history.index = _naive_datetime_index(history.index)
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    recent = history.loc[
        (history.index <= cutoff)
        & (history.index >= cutoff - pd.Timedelta(days=365))
    ]
    if recent.empty:
        return features

    grades = recent.get("ToGrade", pd.Series(index=recent.index, dtype=object)).map(
        _rating_score
    ).dropna()
    if not grades.empty:
        features["analyst_rating_mean_1y"] = float(grades.mean())
        features["analyst_buy_share_1y"] = float((grades <= 2).mean())

    actions = recent.get("Action", pd.Series(index=recent.index, dtype=object))
    actions = actions.astype(str).str.lower()
    if len(actions):
        features["analyst_downgrade_share_1y"] = float(actions.str.contains("down").mean())
        features["analyst_action_count_1y"] = float(np.log1p(len(actions)))

    targets = pd.to_numeric(recent.get("currentPriceTarget"), errors="coerce")
    targets = targets.loc[targets > 0]
    if np.isfinite(price) and price > 0 and not targets.empty:
        features["analyst_target_upside_1y"] = float((targets / price - 1).mean())

    prior_targets = pd.to_numeric(recent.get("priorPriceTarget"), errors="coerce")
    current_targets = pd.to_numeric(recent.get("currentPriceTarget"), errors="coerce")
    valid_targets = (prior_targets > 0) & (current_targets > 0)
    if valid_targets.any():
        features["analyst_target_revision_1y"] = float(
            (current_targets[valid_targets] / prior_targets[valid_targets] - 1).mean()
        )
    return features


def _earnings_surprise_features(history, as_of):
    features = {column: np.nan for column in EARNINGS_FEATURE_COLS}
    if not isinstance(history, pd.DataFrame) or history.empty:
        return features

    history = history.copy()
    history.index = _naive_datetime_index(history.index)
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    past = history.loc[history.index <= cutoff].sort_index()
    future = history.loc[
        (history.index > cutoff)
        & (history.index <= cutoff + pd.Timedelta(days=120))
    ].sort_index()
    estimates = pd.to_numeric(future.get("EPS Estimate"), errors="coerce").dropna()
    if not estimates.empty:
        next_estimate = float(estimates.iloc[0])
        features["next_quarter_eps_estimate"] = next_estimate
        reported_eps = pd.to_numeric(past.get("Reported EPS"), errors="coerce").dropna()
        if not reported_eps.empty and reported_eps.iloc[-1] != 0:
            features["next_quarter_eps_change"] = (
                next_estimate / float(reported_eps.iloc[-1]) - 1
            )

    recent = history.loc[
        (history.index <= cutoff)
        & (history.index >= cutoff - pd.Timedelta(days=365))
    ]
    surprises = pd.to_numeric(recent.get("Surprise(%)"), errors="coerce").dropna()
    if not surprises.empty:
        features["earnings_surprise_mean_1y"] = float(surprises.mean() / 100)
        features["earnings_beat_rate_1y"] = float((surprises > 0).mean())
        features["earnings_surprise_count_1y"] = float(len(surprises))
    return features


def _recommendation_label(value):
    if not np.isfinite(value):
        return None
    if value <= 1.5:
        return "Strong buy"
    if value <= 2.5:
        return "Buy"
    if value <= 3.5:
        return "Hold"
    if value <= 4.5:
        return "Sell"
    return "Strong sell"


def _statement_value(statement, period, labels):
    for label in labels:
        if label in statement.index:
            value = _number(statement.loc[label, period])
            if np.isfinite(value):
                return value
    return np.nan


def _feature_values(current, previous=None):
    def ratio(numerator, denominator):
        if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator == 0:
            return np.nan
        return numerator / denominator

    def growth(field):
        if previous is None:
            return np.nan
        prior_value = previous.get(field, np.nan)
        current_value = current.get(field, np.nan)
        if not np.isfinite(prior_value) or prior_value == 0 or not np.isfinite(current_value):
            return np.nan
        return current_value / prior_value - 1

    market_cap = current.get("market_cap", np.nan)
    revenue = current.get("revenue", np.nan)
    total_assets = current.get("total_assets", np.nan)
    total_debt = current.get("total_debt", np.nan)
    net_income = current.get("net_income", np.nan)
    net_issuance = current.get("net_issuance", np.nan)
    analyst_upside = current.get("analyst_target_upside_1y", np.nan)
    earnings_beat_rate = current.get("earnings_beat_rate_1y", np.nan)
    undervaluation_beat_signal = (
        max(analyst_upside, 0) * earnings_beat_rate
        if np.isfinite(analyst_upside) and np.isfinite(earnings_beat_rate)
        else np.nan
    )
    return {
        "log_cap": np.log1p(max(market_cap, 0)) if np.isfinite(market_cap) else np.nan,
        "log_revenue": np.log1p(max(revenue, 0)) if np.isfinite(revenue) else np.nan,
        "earnings_yield": ratio(net_income, market_cap),
        "revenue_yield": ratio(revenue, market_cap),
        "fcf_yield": ratio(current.get("free_cash_flow", np.nan), market_cap),
        "ocf_yield": ratio(current.get("operating_cash_flow", np.nan), market_cap),
        "debt_assets": ratio(current.get("total_debt", np.nan), current.get("total_assets", np.nan)),
        "issuance_yield": ratio(current.get("net_issuance", np.nan), market_cap),
        "repurchase_yield": ratio(current.get("repurchase", np.nan), market_cap),
        "sbc_revenue": ratio(current.get("stock_compensation", np.nan), revenue),
        "earnings_growth": growth("net_income"),
        "revenue_growth": growth("revenue"),
        "eps_growth": growth("eps"),
        "log_assets": np.log1p(max(total_assets, 0)) if np.isfinite(total_assets) else np.nan,
        "log_debt": np.log1p(max(total_debt, 0)) if np.isfinite(total_debt) else np.nan,
        "signed_log_income": (
            np.sign(net_income) * np.log1p(abs(net_income))
            if np.isfinite(net_income)
            else np.nan
        ),
        "signed_log_issuance": (
            np.sign(net_issuance) * np.log1p(abs(net_issuance))
            if np.isfinite(net_issuance)
            else np.nan
        ),
        **{column: _number(current.get(column)) for column in PRICE_FEATURE_COLS},
        **{column: _number(current.get(column)) for column in ANALYST_FEATURE_COLS},
        **{column: _number(current.get(column)) for column in EARNINGS_FEATURE_COLS},
        "undervaluation_beat_signal": undervaluation_beat_signal,
    }


def _statement_record(ticker, period, income, balance, cashflow, close, price_date):
    shares = _statement_value(
        income, period, ["Diluted Average Shares", "Basic Average Shares"]
    )
    return {
        "ticker": ticker,
        "fiscal_date": pd.Timestamp(period).tz_localize(None),
        "price_date": price_date,
        "close": close,
        "market_cap": close * shares if np.isfinite(close) and np.isfinite(shares) else np.nan,
        "net_income": _statement_value(
            income, period, ["Net Income", "Net Income Common Stockholders"]
        ),
        "revenue": _statement_value(income, period, ["Total Revenue"]),
        "eps": _statement_value(income, period, ["Diluted EPS", "Basic EPS"]),
        "total_debt": _statement_value(balance, period, ["Total Debt"]),
        "total_assets": _statement_value(balance, period, ["Total Assets"]),
        "free_cash_flow": _statement_value(cashflow, period, ["Free Cash Flow"]),
        "operating_cash_flow": _statement_value(
            cashflow, period, ["Operating Cash Flow"]
        ),
        "net_issuance": _statement_value(
            cashflow, period, ["Net Common Stock Issuance"]
        ),
        "repurchase": _statement_value(
            cashflow, period, ["Repurchase Of Capital Stock"]
        ),
        "stock_compensation": _statement_value(
            cashflow, period, ["Stock Based Compensation"]
        ),
    }


def download_yahoo_data(tickers=None, output_dir=YAHOO_DATA_DIR):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tickers = tickers or yahoo_ticker_universe()
    downloaded = 0

    for symbol in tickers:
        try:
            stock = yf.Ticker(symbol)
            income = stock.income_stmt
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            prices = stock.history(period="5y", auto_adjust=False)
            if income.empty or balance.empty or cashflow.empty or prices.empty:
                print(f"{symbol}: Yahoo returned incomplete annual data")
                continue

            price_index = pd.DatetimeIndex(prices.index)
            if price_index.tz is not None:
                price_index = price_index.tz_localize(None)
            prices.index = price_index
            try:
                analyst_history = stock.upgrades_downgrades
            except Exception:
                analyst_history = pd.DataFrame()
            try:
                earnings_dates = stock.get_earnings_dates(limit=50)
            except Exception:
                earnings_dates = pd.DataFrame()

            records = []
            periods = set(income.columns) & set(balance.columns) & set(cashflow.columns)
            for period in sorted(periods):
                fiscal_date = pd.Timestamp(period)
                if fiscal_date.tzinfo is not None:
                    fiscal_date = fiscal_date.tz_localize(None)
                available_date = fiscal_date + pd.Timedelta(days=90)
                available_prices = prices.loc[prices.index >= available_date]
                if available_prices.empty:
                    continue
                price_date = available_prices.index[0]
                close = _number(available_prices.iloc[0].get("Close"))
                record = _statement_record(
                    symbol,
                    fiscal_date,
                    income,
                    balance,
                    cashflow,
                    close,
                    price_date,
                )
                record.update(_price_behavior_features(prices, price_date))
                record.update(
                    _analyst_history_features(analyst_history, price_date, close)
                )
                record.update(_earnings_surprise_features(earnings_dates, price_date))
                records.append(record)

            if not records:
                print(f"{symbol}: no annual rows with a post-reporting price")
                continue

            pd.DataFrame(records).sort_values("fiscal_date").to_csv(
                output_dir / f"{symbol}_annual.csv", index=False
            )
            downloaded += 1
            print(f"{symbol}: saved {len(records)} Yahoo annual rows")
        except Exception as error:
            print(f"{symbol}: Yahoo fetch failed ({type(error).__name__})")
        time.sleep(0.2)

    return downloaded


def refresh_yahoo_price_features(data_dir=YAHOO_DATA_DIR):
    data_dir = Path(data_dir)
    refreshed = 0
    for path in sorted(data_dir.glob("*_annual.csv")):
        try:
            data = pd.read_csv(path, low_memory=False)
            if data.empty:
                continue
            symbol = str(data.iloc[0]["ticker"])
            stock = yf.Ticker(symbol)
            prices = stock.history(period="5y", auto_adjust=False)
            if prices.empty:
                print(f"{symbol}: Yahoo returned no price history")
                continue
            try:
                analyst_history = stock.upgrades_downgrades
            except Exception:
                analyst_history = pd.DataFrame()
            try:
                earnings_dates = stock.get_earnings_dates(limit=50)
            except Exception:
                earnings_dates = pd.DataFrame()
            for index, row in data.iterrows():
                as_of = pd.to_datetime(row.get("price_date"), errors="coerce")
                values = _price_behavior_features(prices, as_of)
                values.update(
                    _analyst_history_features(
                        analyst_history, as_of, _number(row.get("close"))
                    )
                )
                values.update(_earnings_surprise_features(earnings_dates, as_of))
                for column, value in values.items():
                    data.at[index, column] = value
            data.to_csv(path, index=False)
            refreshed += 1
            print(f"{symbol}: refreshed {len(data)} Yahoo price feature rows")
        except Exception as error:
            print(f"{path.stem}: Yahoo price refresh failed ({type(error).__name__})")
        time.sleep(0.2)
    return refreshed


def load_yahoo_training_data(data_dir=YAHOO_DATA_DIR):
    data_dir = Path(data_dir)
    files = sorted(data_dir.glob("*_annual.csv"))
    if not files:
        raise RuntimeError("No Yahoo annual data. Run `uv run yahoo_data.py` first.")

    frames = [pd.read_csv(path, low_memory=False) for path in files]
    data = pd.concat(frames, ignore_index=True)
    data["fiscal_date"] = pd.to_datetime(data["fiscal_date"], errors="coerce")
    numeric_columns = [
        "market_cap", "net_income", "revenue", "eps", "total_debt", "total_assets",
        "free_cash_flow", "operating_cash_flow", "net_issuance", "repurchase",
        "stock_compensation", *PRICE_FEATURE_COLS,
        *ANALYST_FEATURE_COLS, *EARNINGS_FEATURE_COLS,
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.dropna(subset=["ticker", "fiscal_date"]).sort_values(
        ["ticker", "fiscal_date"]
    )

    feature_rows = []
    for _, ticker_rows in data.groupby("ticker", sort=False):
        previous = None
        for _, row in ticker_rows.iterrows():
            current = row.to_dict()
            feature_rows.append(_feature_values(current, previous))
            previous = current

    engineered = pd.DataFrame(feature_rows, index=data.index)
    data[FEATURE_COLS] = engineered[FEATURE_COLS]
    data["future_net_issuance"] = data.groupby("ticker")["net_issuance"].shift(-1)
    data["dilution_signal"] = np.sign(data["future_net_issuance"])
    return data


def build_live_model_features(stock, info):
    income = stock.income_stmt
    balance = stock.balance_sheet
    cashflow = stock.cashflow
    periods = sorted(
        set(income.columns) & set(balance.columns) & set(cashflow.columns), reverse=True
    )
    if not periods:
        raise RuntimeError("Yahoo returned no matching annual financial statements.")

    current = _statement_record(
        stock.ticker,
        periods[0],
        income,
        balance,
        cashflow,
        _number(info.get("currentPrice") or info.get("regularMarketPrice")),
        pd.NaT,
    )
    previous = (
        _statement_record(
            stock.ticker,
            periods[1],
            income,
            balance,
            cashflow,
            np.nan,
            pd.NaT,
        )
        if len(periods) > 1
        else None
    )
    prices = stock.history(period="2y", auto_adjust=False)
    if not prices.empty:
        current.update(_price_behavior_features(prices, prices.index[-1]))
    try:
        current.update(
            _analyst_history_features(
                stock.upgrades_downgrades,
                prices.index[-1] if not prices.empty else pd.Timestamp.now(),
                current["close"],
            )
        )
    except Exception:
        pass
    try:
        current.update(
            _earnings_surprise_features(
                stock.get_earnings_dates(limit=50),
                prices.index[-1] if not prices.empty else pd.Timestamp.now(),
            )
        )
    except Exception:
        pass
    return _feature_values(current, previous)


def fetch_yahoo_outlook(symbol, stock=None, info=None):
    stock = stock or yf.Ticker(symbol)
    if info is None:
        try:
            info = stock.info
        except Exception:
            info = {}

    outlook = {
        "eps_estimate": np.nan,
        "eps_growth": np.nan,
        "revenue_estimate": np.nan,
        "revenue_growth": np.nan,
        "recommendation_mean": _number(info.get("recommendationMean")),
        "recommendation_label": _recommendation_label(
            _number(info.get("recommendationMean"))
        ),
        "rating_counts": {},
        "target_mean": np.nan,
        "target_upside": np.nan,
        "news_sentiment": np.nan,
        "shortage_mentions": 0,
        "headlines": [],
    }

    for table_name, estimate_key, growth_key in [
        ("earnings_estimate", "eps_estimate", "eps_growth"),
        ("revenue_estimate", "revenue_estimate", "revenue_growth"),
    ]:
        try:
            table = getattr(stock, table_name)
            if "+1y" in table.index:
                outlook[estimate_key] = _number(table.loc["+1y", "avg"])
                outlook[growth_key] = _number(table.loc["+1y", "growth"])
        except Exception:
            pass

    try:
        recommendations = stock.recommendations_summary
        if not recommendations.empty:
            current = recommendations.loc[recommendations["period"] == "0m"]
            row = current.iloc[0] if not current.empty else recommendations.iloc[0]
            for column in ["strongBuy", "buy", "hold", "sell", "strongSell"]:
                count = _number(row.get(column))
                outlook["rating_counts"][column] = int(count) if np.isfinite(count) else 0
    except Exception:
        pass

    try:
        targets = stock.analyst_price_targets
        current_price = _number(
            info.get("currentPrice") or info.get("regularMarketPrice")
        )
        target_mean = _number(targets.get("mean")) if isinstance(targets, dict) else np.nan
        outlook["target_mean"] = target_mean
        if np.isfinite(target_mean) and np.isfinite(current_price) and current_price > 0:
            outlook["target_upside"] = target_mean / current_price - 1
    except Exception:
        pass

    try:
        news = yf.Search(symbol, news_count=15).news
        headlines = [item for item in news if item.get("title")]
        if headlines:
            scores = [
                SENTIMENT_ANALYZER.polarity_scores(item["title"])["compound"]
                for item in headlines
            ]
            outlook["news_sentiment"] = float(np.mean(scores))
            outlook["shortage_mentions"] = sum(
                bool(SHORTAGE_PATTERN.search(item["title"])) for item in headlines
            )
            outlook["headlines"] = [
                {
                    "title": item["title"],
                    "publisher": item.get("publisher", "Yahoo Finance"),
                    "link": item.get("link", ""),
                }
                for item in headlines[:4]
            ]
    except Exception:
        pass

    return outlook


if __name__ == "__main__":
    download_yahoo_data()