from flask import render_template, request, flash
from flask_login import login_required
import pandas as pd
import yfinance as yf
import os
from .algorith import StockPredictor

@bp.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    prediction = None
    ticker = None
    graph1 = None
    graph2 = None
    graph3 = None
    error_message = None

    if request.method == "POST":
        ticker = request.form.get('ticker', '').upper()
        
        if not ticker:
            error_message = "Please enter a stock ticker"
        else:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period="1mo")
                
                if hist.empty:
                    error_message = f"No data found for ticker: {ticker}"
                else:
                    financials = stock.financials
                    balance_sheet = stock.balance_sheet
                    cashflow = stock.cashflow

                    data = {
                        "marketPrice": info.get('currentPrice', 0),
                        "sharesOutstanding": info.get('sharesOutstanding', 0),
                        "freeCashFlow": info.get('freeCashflow', 0),
                        "operatingCashFlow": info.get('operatingCashflow', 0),
                        "totalDebt": info.get('totalDebt', 0),
                        "dividendsPaid": cashflow.loc['Cash Dividends Paid'].iloc[0] if not cashflow.empty and 'Cash Dividends Paid' in cashflow.index else 0,
                        "netIncome": info.get('netIncomeToCommon', 0),
                        "employees": info.get('fullTimeEmployees', 0),
                        "stockIssued": cashflow.loc['Issuance Of Capital Stock'].iloc[0] if not cashflow.empty and 'Issuance Of Capital Stock' in cashflow.index else 0,
                        "stockRepurchased": cashflow.loc['Repurchase Of Capital Stock'].iloc[0] if not cashflow.empty and 'Repurchase Of Capital Stock' in cashflow.index else 0,
                    }

                    if predictor:
                        df_input = pd.DataFrame([data])
                        result = predictor.predict(df_input)
                        prediction = (result[0])
                    
                    hist_reset = hist.reset_index()
                    fig1 = px.line(
                        hist_reset, 
                        x='Date', 
                        y='Close',
                        title=f'{ticker} Stock Price - Last 30 Days',
                        labels={'Close': 'Price ($)', 'Date': 'Date'}
                    )
                    graph1 = fig1.to_html(full_html=False)

                    volume_data = hist['Volume'].tail(30)
                    avg_volume = volume_data.mean()
                    
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(
                        x=hist_reset['Date'].tail(30),
                        y=volume_data,
                        name='Daily Volume',
                    ))
                    fig2.add_trace(go.Scatter(
                        x=hist_reset['Date'].tail(30),
                        y=[avg_volume] * len(volume_data),
                        name='Average Volume',
                        line=dict(color='red', dash='dash', width=2)
                    ))
                    fig2.update_layout(
                        title=f'{ticker} Trading Volume - Last 30 Days',
                        xaxis_title='Date',
                        yaxis_title='Volume'
                    )
                    graph2 = fig2.to_html(full_html=False)

                    metrics = {
                        'Market Cap': info.get('marketCap', 0) / 1e9,
                        'Total Debt': data['totalDebt'] / 1e9 if data['totalDebt'] else 0,
                        'Free Cash Flow': data['freeCashFlow'] / 1e9 if data['freeCashFlow'] else 0,
                        'Net Income': data['netIncome'] / 1e9 if data['netIncome'] else 0,
                    }
                    
                    metrics = {k: v for k, v in metrics.items() if v != 0}
                    
                    if metrics:
                        fig3 = px.bar(
                            x=list(metrics.keys()),
                            y=list(metrics.values()),
                            title=f'{ticker} Key Financial Metrics (Billions $)',
                            labels={'x': 'Metric', 'y': 'Value (Billions $)'},
                            color=list(metrics.values()),
                            color_continuous_scale='Blues'
                        )
                        graph3 = fig3.to_html(full_html=False)
                    else:
                        fig3 = px.pie(names=['Data Unavailable'], values=[100])
                        graph3 = fig3.to_html(full_html=False)

            except Exception as e:
                error_message = f"Error analyzing {ticker}: {str(e)}"

    if not graph1:
        days = list(range(1, 31))
        sample_prices = [100 + i * 2 for i in days]
        fig1 = px.line(x=days, y=sample_prices, title='Stock Price - Enter ticker')
        graph1 = fig1.to_html(full_html=False)

    if not graph2:
        fig2 = px.bar(x=['Week 1', 'Week 2', 'Week 3', 'Week 4'], 
                      y=[1000000, 1200000, 950000, 1100000], 
                      title='Trading Volume - Enter ticker')
        graph2 = fig2.to_html(full_html=False)

    if not graph3:
        fig3 = px.bar(x=['Market Cap', 'Revenue', 'Profit', 'Debt'], 
                      y=[100, 75, 25, 30], 
                      title='Financial Metrics - Enter ticker')
        graph3 = fig3.to_html(full_html=False)

    return render_template(
        "dashboard.html",
        active="dashboard",
        graph1=graph1,
        graph2=graph2,
        graph3=graph3,
        prediction=prediction,
        ticker=ticker,
    )
