import yfinance as yf
import pandas as pd
import os
from datetime import datetime
import shutil

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

os.makedirs(output_dir, exist_ok=True)

for ticker in tickers:
    print(f"Downloading {ticker}...")

    data = yf.download(ticker, start=start_date, end=end_date, interval="1d")

    if data.empty:
        print(f"⚠️ No data for {ticker}, skipping.")
        continue

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = ["_".join(col).strip() for col in data.columns.values]

    data["Year"] = data.index.year

    fundamentals = pd.DataFrame(index=data.index)

    try:
        stock = yf.Ticker(ticker)

        info = stock.info if hasattr(stock, "info") else {}
        if "sharesOutstanding" in info:
            fundamentals["SharesOutstanding"] = info["sharesOutstanding"]

        divs = stock.dividends
        if not divs.empty:
            fundamentals = fundamentals.join(divs.rename("Dividends"), how="left")

        splits = stock.splits
        if not splits.empty:
            fundamentals = fundamentals.join(splits.rename("Splits"), how="left")

        fin = stock.quarterly_financials.T
        bs = stock.quarterly_balance_sheet.T
        cf = stock.quarterly_cashflow.T

        if (
            not fin.empty or not bs.empty or not cf.empty
        ):  # this became redudant wamp wamp
            fin_bs_cf = pd.DataFrame(index=fin.index.union(bs.index).union(cf.index))
            fin_bs_cf["TotalRevenue"] = fin.get("Total Revenue")
            fin_bs_cf["GrossProfit"] = fin.get("Gross Profit")
            fin_bs_cf["OperatingIncome"] = fin.get("Operating Income")
            fin_bs_cf["NetIncome"] = fin.get("Net Income")
            fin_bs_cf["TotalAssets"] = bs.get("Total Assets")
            fin_bs_cf["TotalLiab"] = bs.get("Total Liab")
            fin_bs_cf["CommonStock"] = bs.get("Common Stock")
            fin_bs_cf["OperatingCashFlow"] = cf.get(
                "Total Cash From Operating Activities"
            )
            fin_bs_cf["CapEx"] = cf.get("Capital Expenditures")

            fin_bs_cf["DebtToEquity"] = fin_bs_cf["TotalLiab"] / (
                fin_bs_cf["TotalAssets"] - fin_bs_cf["TotalLiab"]
            )
            fin_bs_cf["FreeCashFlow"] = (
                fin_bs_cf["OperatingCashFlow"] + fin_bs_cf["CapEx"]
            )

            fin_bs_cf = fin_bs_cf.sort_index()
            fin_bs_cf = fin_bs_cf.reindex(data.index, method="ffill")

            fundamentals = pd.concat([fundamentals, fin_bs_cf], axis=1)

    except Exception as e:
        print(f"⚠️ Fundamentals fetch failed for {ticker}: {e}")

    merged = pd.concat([data, fundamentals], axis=1)

    for year, df_year in merged.groupby("Year"):
        df_year = df_year.drop(columns=["Year"], errors="ignore")
        file_path = f"{output_dir}/{ticker}_{year}.csv"
        df_year.to_csv(file_path)
        print(f"✔️ Saved {file_path}")

    merged = pd.concat([data, fundamentals], axis=1)

    for year, df_year in merged.groupby("Year"):
        df_year = df_year.drop(columns=["Year"], errors="ignore")
        file_path = f"{output_dir}/{ticker}_{year}.csv"
        df_year.to_csv(file_path)
        print(f"✔️ Saved {file_path}")
