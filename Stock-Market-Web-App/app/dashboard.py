from flask import render_template, request, flash
from flask_login import login_required
import pandas as pd
import yfinance as yf
import os
from app.algorith import StockPredictor 

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "alg/model.pkl")
SCALER_PATH = os.path.join(BASE_DIR, "alg/scaler.pkl")
COLS_PATH = os.path.join(BASE_DIR, "alg/columns.pkl")

predictor = StockPredictor(MODEL_PATH, SCALER_PATH, COLS_PATH)

@bp.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    prediction = None
    ticker = None

    if request.method == 'POST':
        ticker = request.form.get('ticker').upper()
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            financials = stock.financials
            balance_sheet = stock.balance_sheet
            cashflow = stock.cashflow

            data = {
                "marketPrice": info.get('currentPrice', 0),
                "sharesOutstanding": info.get('sharesOutstanding', 0),
                "freeCashFlow": info.get('freeCashflow', 0),
                "operatingCashFlow": info.get('operatingCashflow', 0),
                "totalDebt": info.get('totalDebt', 0),
                "dividendsPaid": cashflow.loc['Cash Dividends Paid'].iloc[0] if 'Cash Dividends Paid' in cashflow.index else 0,
                "netIncome": info.get('netIncomeToCommon', 0),
                "employees": info.get('fullTimeEmployees', 0),
                "stockIssued": cashflow.loc['Issuance Of Capital Stock'].iloc[0] if 'Issuance Of Capital Stock' in cashflow.index else 0,
                "stockRepurchased": cashflow.loc['Repurchase Of Capital Stock'].iloc[0] if 'Repurchase Of Capital Stock' in cashflow.index else 0,
            }

            df_input = pd.DataFrame([data])

            result = predictor.predict(df_input)
            
            prediction = result[0] 

        except Exception as e:
            flash(f"Error analyzing {ticker}: {str(e)}")

    return render_template('dashboard.html', prediction=prediction)
