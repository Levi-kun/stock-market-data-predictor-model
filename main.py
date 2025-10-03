import yfinance as yf
import pandas as pd
import os
from datetime import datetime
import shutil

# === SETTINGS ===
tickers = [
    "NVDA",
    "AAPL",
    "MSFT",
    "TSLA",
    "ORCL",
    "META",
    "GOOG",
    "JPM",
    "TSM",
    "XOM",
]  # added some non tech companies so it's more general
start_date = (
    "1988-01-01"  # since it's tech centric trying to push it before the dot com bubble
)

end_date = datetime.today().strftime("%Y-%m-%d")
output_dir = "datasets"

if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir, exist_ok=True)

for ticker in tickers:
    print(f"Downloading {ticker}...")

    data = yf.download(ticker, start=start_date, end=end_date, interval="1d")

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = ["_".join(col).strip() for col in data.columns.values]

    data["Year"] = data.index.year

    stock = yf.Ticker(ticker)

    fin = stock.quarterly_financials.T
    bs = stock.quarterly_balance_sheet.T
    cf = stock.quarterly_cashflow.T

    fundamentals = pd.DataFrame(index=fin.index)
    fundamentals["TotalRevenue"] = fin.get("Total Revenue")
    fundamentals["GrossProfit"] = fin.get("Gross Profit")
    fundamentals["OperatingIncome"] = fin.get("Operating Income")
    fundamentals["NetIncome"] = fin.get("Net Income")
    fundamentals["TotalAssets"] = bs.get("Total Assets")
    fundamentals["TotalLiab"] = bs.get("Total Liab")
    fundamentals["CommonStock"] = bs.get("Common Stock")
    fundamentals["OperatingCashFlow"] = cf.get("Total Cash From Operating Activities")
    fundamentals["CapEx"] = cf.get("Capital Expenditures")

    fundamentals["DebtToEquity"] = fundamentals["TotalLiab"] / (
        fundamentals["TotalAssets"] - fundamentals["TotalLiab"]
    )
    fundamentals["FreeCashFlow"] = (
        fundamentals["OperatingCashFlow"] + fundamentals["CapEx"]
    )

    fundamentals = fundamentals.sort_index()
    fundamentals = fundamentals.reindex(data.index, method="ffill")

    merged = data.join(fundamentals)

    for year, df_year in merged.groupby("Year"):
        df_year = df_year.drop(columns=["Year"])
        df_year.to_csv(f"{output_dir}/{ticker}_{year}.csv")
