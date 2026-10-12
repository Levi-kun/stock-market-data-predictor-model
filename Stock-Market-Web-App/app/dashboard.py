from flask import request, flash, render_template
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os
import math
import sys

from .ticker_store import get_prediction_history, register_ticker, save_prediction

try:
    from .algorith import StockPredictor
except ImportError:
    # If running as standalone or algorith module doesn't exist
    StockPredictor = None

# --- Setup Paths & Model ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
PROJECT_ROOT = os.path.abspath(os.path.join(ROOT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from yahoo_data import build_live_model_features, fetch_yahoo_outlook

MODEL_PATH = os.path.join(ROOT_DIR, "alg/model.pkl")
SCALER_PATH = os.path.join(ROOT_DIR, "alg/scaler.pkl")
COLS_PATH = os.path.join(ROOT_DIR, "alg/columns.pkl")

# Initialize Predictor safely once when the module loads
predictor = None
if StockPredictor:
    try:
        predictor = StockPredictor(MODEL_PATH, SCALER_PATH, COLS_PATH)
    except Exception as e:
        print(f"Warning: StockPredictor model could not load. {e}")


def build_stock_data(info, cashflow):
    def get_val(key):
        if cashflow is not None and not cashflow.empty and key in cashflow.index:
            value = cashflow.loc[key].iloc[0]
            return 0 if pd.isna(value) else value
        return 0

    return {
        "marketPrice": info.get("currentPrice", 0) or 0,
        "sharesOutstanding": info.get("sharesOutstanding", 0) or 0,
        "freeCashFlow": info.get("freeCashflow", 0) or 0,
        "operatingCashFlow": info.get("operatingCashflow", 0) or 0,
        "totalDebt": info.get("totalDebt", 0) or 0,
        "dividendsPaid": get_val("Cash Dividends Paid"),
        "netIncome": info.get("netIncomeToCommon", 0) or 0,
        "employees": info.get("fullTimeEmployees", 0) or 0,
        "stockIssued": get_val("Issuance Of Capital Stock"),
        "stockRepurchased": get_val("Repurchase Of Capital Stock"),
    }


def predict_ticker(ticker):
    if predictor is None:
        raise RuntimeError("Prediction model is unavailable.")

    stock = yf.Ticker(ticker)
    info = stock.info
    result = predictor.predict(
        pd.DataFrame([build_live_model_features(stock, info)])
    )
    return float(result[0])


def get_dashboard_data():
    """
    Processes the dashboard logic and returns all data needed for rendering.
    Returns a dictionary with prediction, ticker, and graph HTML strings.
    """
    data = {
        "prediction": None,
        "ticker": None,
        "graph1": None,
        "graph2": None,
        "graph3": None,
        "outlook": None,
    }

    if request.method == "POST":
        # Fixed: changed from "shout" to "ticker" to match the input name
        ticker = request.form.get("ticker", "").strip().upper()

        if not ticker:
            flash("Please enter a ticker symbol.", "error")
        else:
            try:
                # 1. Fetch Data
                stock = yf.Ticker(ticker)
                hist = stock.history(period="1mo")
                info = stock.info

                # Check if we got valid data
                if hist.empty:
                    flash(
                        f"No data found for ticker {ticker}. Please check the symbol.",
                        "error",
                    )
                    return data

                register_ticker(ticker)

                # Safely get cashflow
                try:
                    cashflow = stock.cashflow
                except Exception:
                    cashflow = pd.DataFrame()

                # 2. Prepare Data for Model
                stock_data = build_stock_data(info, cashflow)
                data["outlook"] = fetch_yahoo_outlook(ticker, stock, info)

                # 3. Predict
                if predictor:
                    try:
                        features = build_live_model_features(stock, info)
                        df_input = pd.DataFrame([features])
                        result = predictor.predict(df_input)
                        prediction_value = float(result[0])
                        if math.isfinite(prediction_value):
                            data["prediction"] = prediction_value
                            save_prediction(ticker, prediction_value)
                        else:
                            data["prediction"] = "N/A"
                    except Exception as e:
                        print(f"Prediction error: {e}")
                        data["prediction"] = "N/A"
                else:
                    data["prediction"] = "Model not available"

                # 4. Generate Graphs
                if not hist.empty:
                    hist_reset = hist.reset_index()

                    # -- Graph 1: Price --
                    price_dates = hist_reset["Date"].dt.strftime("%Y-%m-%d")
                    fig1 = go.Figure()
                    fig1.add_trace(
                        go.Scatter(
                            x=price_dates,
                            y=hist_reset["Close"],
                            name="Stock price",
                            line=dict(color="#1f77b4", width=2),
                        )
                    )
                    prediction_history = get_prediction_history(ticker, days=30)
                    if prediction_history:
                        fig1.add_trace(
                            go.Scatter(
                                x=[row[0].isoformat() for row in prediction_history],
                                y=[row[1] for row in prediction_history],
                                name="Predictor value",
                                yaxis="y2",
                                line=dict(color="#176b50", width=2),
                            )
                        )
                    fig1.update_layout(
                        title=f"{ticker} Stock Price and Predictor Value",
                        xaxis_title="Date",
                        yaxis=dict(title="Price ($)"),
                        yaxis2=dict(
                            title="Predictor value",
                            overlaying="y",
                            side="right",
                            range=[-1, 1],
                            tickvals=[-1, 0, 1],
                            ticktext=["-1", "0", "+1"],
                            zeroline=True,
                        ),
                        hovermode="x unified",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="gray"),
                        margin=dict(l=40, r=40, t=40, b=40),
                    )
                    data["graph1"] = fig1.to_html(
                        full_html=False, include_plotlyjs="cdn"
                    )

                    # -- Graph 2: Volume --
                    volume_data = hist["Volume"].tail(30)
                    avg_volume = volume_data.mean()

                    fig2 = go.Figure()
                    fig2.add_trace(
                        go.Bar(
                            x=hist_reset["Date"].tail(30),
                            y=volume_data,
                            name="Daily Volume",
                            marker_color="#1f77b4",
                        )
                    )
                    fig2.add_trace(
                        go.Scatter(
                            x=hist_reset["Date"].tail(30),
                            y=[avg_volume] * len(volume_data),
                            name="Average Volume",
                            line=dict(color="red", dash="dash", width=2),
                        )
                    )
                    fig2.update_layout(
                        title=f"{ticker} Trading Volume",
                        xaxis_title="Date",
                        yaxis_title="Volume",
                        hovermode="x unified",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="gray"),
                        margin=dict(l=40, r=40, t=40, b=40),
                    )
                    data["graph2"] = fig2.to_html(
                        full_html=False, include_plotlyjs="cdn"
                    )

                    # -- Graph 3: Financial Metrics --
                    metrics = {
                        "Market Cap": (
                            info.get("marketCap", 0) / 1e9
                            if info.get("marketCap")
                            else 0
                        ),
                        "Total Debt": (
                            stock_data["totalDebt"] / 1e9
                            if stock_data["totalDebt"]
                            else 0
                        ),
                        "Free Cash Flow": (
                            stock_data["freeCashFlow"] / 1e9
                            if stock_data["freeCashFlow"]
                            else 0
                        ),
                        "Net Income": (
                            stock_data["netIncome"] / 1e9
                            if stock_data["netIncome"]
                            else 0
                        ),
                    }
                    # Remove 0 values
                    metrics = {k: v for k, v in metrics.items() if v != 0}

                    if metrics:
                        fig3 = px.bar(
                            x=list(metrics.keys()),
                            y=list(metrics.values()),
                            title=f"{ticker} Key Financials ($B)",
                            labels={"x": "Metric", "y": "Billions ($)"},
                            color=list(metrics.values()),
                            color_continuous_scale="Blues",
                        )
                        fig3.update_layout(
                            showlegend=False,
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="gray"),
                            margin=dict(l=40, r=40, t=40, b=40),
                        )
                        data["graph3"] = fig3.to_html(
                            full_html=False, include_plotlyjs="cdn"
                        )
                    else:
                        data["graph3"] = (
                            '<div style="color: gray; padding: 20px; text-align: center;">'
                            "No financial data available</div>"
                        )

                # Set ticker after successful processing
                data["ticker"] = ticker
                flash(f"Successfully analyzed {ticker}", "success")

            except Exception as e:
                flash(f"Error analyzing {ticker}: {str(e)}", "error")
                print(f"DEBUG ERROR: {e}")
                import traceback

                traceback.print_exc()

    return data
