from flask import request, flash, render_template
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
import os

try:
    from .algorith import StockPredictor
except ImportError:
    # If running as standalone or algorith module doesn't exist
    StockPredictor = None

# --- Setup Paths & Model ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

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

                # Safely get cashflow
                try:
                    cashflow = stock.cashflow
                except Exception:
                    cashflow = pd.DataFrame()

                # 2. Prepare Data for Model
                def get_val(df, key):
                    if df is not None and not df.empty and key in df.index:
                        val = df.loc[key].iloc[0]
                        # Handle NaN values
                        return 0 if pd.isna(val) else val
                    return 0

                stock_data = {
                    "marketPrice": info.get("currentPrice", 0) or 0,
                    "sharesOutstanding": info.get("sharesOutstanding", 0) or 0,
                    "freeCashFlow": info.get("freeCashflow", 0) or 0,
                    "operatingCashFlow": info.get("operatingCashflow", 0) or 0,
                    "totalDebt": info.get("totalDebt", 0) or 0,
                    "dividendsPaid": get_val(cashflow, "Cash Dividends Paid"),
                    "netIncome": info.get("netIncomeToCommon", 0) or 0,
                    "employees": info.get("fullTimeEmployees", 0) or 0,
                    "stockIssued": get_val(cashflow, "Issuance Of Capital Stock"),
                    "stockRepurchased": get_val(
                        cashflow, "Repurchase Of Capital Stock"
                    ),
                }

                # 3. Predict
                if predictor:
                    try:
                        df_input = pd.DataFrame([stock_data])
                        result = predictor.predict(df_input)
                        data["prediction"] = result[0]
                    except Exception as e:
                        print(f"Prediction error: {e}")
                        data["prediction"] = "N/A"
                else:
                    data["prediction"] = "Model not available"

                # 4. Generate Graphs
                if not hist.empty:
                    hist_reset = hist.reset_index()

                    # -- Graph 1: Price --
                    fig1 = px.line(
                        hist_reset,
                        x="Date",
                        y="Close",
                        title=f"{ticker} Stock Price - Last 30 Days",
                        labels={"Close": "Price ($)", "Date": "Date"},
                    )
                    fig1.update_traces(line_color="#1f77b4", line_width=2)
                    fig1.update_layout(
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
