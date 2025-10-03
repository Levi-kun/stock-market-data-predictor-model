import yfinance as yf
import pandas as pd
import os
import pandas.api.types as ptypes
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
]

start_date = "1988-01-01"

end_date = datetime.today().strftime("%Y-%m-%d")
output_dir = "datasets"

os.makedirs(output_dir, exist_ok=True)

for ticker in tickers:
    print(f"Fetching data for {ticker}...")

    data = yf.download(ticker, start=start_date, end=end_date, interval="1d")

    if data.empty:
        print(f"No data for {ticker}, skipping.")
        continue

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = ["_".join(col).strip() for col in data.columns.values]

    data["Year"] = data.index.year
    fundamentals = pd.DataFrame(index=data.index)

    try:
        stock = yf.Ticker(ticker)

        info = stock.info if hasattr(stock, "info") else {}
        for key, val in info.items():
            if ptypes.is_scalar(val) and (
                not isinstance(val, str) or len(str(val)) < 150
            ):
                fundamentals[key] = val

        # FIXED: Shares handling - historical first, fallback with back-adjust if needed
        shares = stock.get_shares_full(start=start_date, end=end_date)
        current_shares = info.get("sharesOutstanding", pd.NA)

        if not shares.empty:
            shares_daily = shares.reindex(data.index, method="ffill").ffill()
            fundamentals["SharesOutstanding"] = shares_daily
            fundamentals["AdjustedSharesOutstanding"] = (
                shares_daily  # Already historical, no adjust
            )
            print(f"Got historical shares for {ticker}.")
        else:
            # Fallback: Scalar current to series
            shares_daily = pd.Series(current_shares, index=data.index)
            fundamentals["SharesOutstanding"] = shares_daily
            print(f"Using current shares for {ticker}: {current_shares:,}.")

            # NEW: Collect buyback events for back-adjustment (only if fallback)
            buyback_events = {}  # q_date: est_shares_reduced (positive)
            quarter_ends = data.resample("Q").last().index.tolist()

            # First, fetch quarterly data (moved up slightly for buybacks)
            fin = stock.quarterly_financials.T
            bs = stock.quarterly_balance_sheet.T
            cf = stock.quarterly_cashflow.T

            if not fin.empty or not bs.empty or not cf.empty:
                all_quarters = pd.concat([fin, bs, cf], axis=1, sort=True)

                # ... (keep existing DebtToEquity, FreeCashFlow logic unchanged)
                if (
                    "Total Liab" in all_quarters.columns
                    and "Total Assets" in all_quarters.columns
                ):
                    equity = all_quarters["Total Assets"] - all_quarters["Total Liab"]
                    all_quarters["DebtToEquity"] = all_quarters[
                        "Total Liab"
                    ] / equity.where(equity != 0, pd.NA)
                if (
                    "Total Cash From Operating Activities" in all_quarters.columns
                    and "Capital Expenditures" in all_quarters.columns
                ):
                    all_quarters["FreeCashFlow"] = (
                        all_quarters["Total Cash From Operating Activities"]
                        + all_quarters["Capital Expenditures"]
                    )

                buyback_col = None
                possible_buyback_cols = [
                    "Repurchase Of Capital Stock",
                    "Common Stock Repurchased",
                    "Purchase Of Treasury Stock",
                    "Stock Repurchase",
                ]
                for col in possible_buyback_cols:
                    if col in all_quarters.columns:
                        buyback_col = col
                        break

                if buyback_col:
                    all_quarters["StockBuybacks"] = all_quarters[buyback_col]
                    print(f"Got buybacks via '{buyback_col}' for {ticker}.")

                # Ffill quarters to daily (unchanged)
                all_quarters = all_quarters.reindex(data.index, method="ffill").ffill()
                fundamentals = pd.concat([fundamentals, all_quarters], axis=1)
                print(f"Fetched quarterly data for {ticker}.")

            # Collect buyback estimates (only for fallback case)
            for q_date in quarter_ends:
                if pd.isna(q_date) or q_date not in all_quarters.index:
                    continue
                q_buyback = (
                    all_quarters.loc[q_date, "StockBuybacks"]
                    if "StockBuybacks" in all_quarters.columns
                    else 0
                )
                if pd.notna(q_buyback) and q_buyback < 0:  # Negative = repurchase
                    q_slice = data[
                        (data.index >= (q_date - pd.DateOffset(months=3)))
                        & (data.index <= q_date)
                    ]
                    avg_price = (
                        q_slice["Close"].mean()
                        if not q_slice.empty
                        else data.loc[q_date, "Close"] if q_date in data.index else None
                    )
                    if pd.notna(avg_price) and avg_price > 0:
                        est_shares_reduced = abs(q_buyback) / avg_price
                        buyback_events[q_date] = est_shares_reduced
                        print(
                            f"Estimated {est_shares_reduced:,.0f} shares reduced for {ticker} at {q_date.date()} (buyback: ${abs(q_buyback):,.0f})"
                        )

            # FIXED: Back-adjust logic (backward cum addback for past dates)
            adjusted_shares = shares_daily.copy()  # Starts as current everywhere
            if buyback_events:
                buyback_dates = sorted(buyback_events.keys())  # Chronological
                cum_addback = 0
                prev_q = data.index[-1] + pd.DateOffset(months=1)  # After last day

                for q in reversed(buyback_dates):  # Recent to past
                    # Dates from this q_date to prev_q get current + current cum_addback
                    mask = (data.index >= q) & (data.index < prev_q)
                    if mask.any():
                        adjusted_shares.loc[
                            mask
                        ] += cum_addback  # Add back future reductions
                    cum_addback += buyback_events[
                        q
                    ]  # Add this reduction for even earlier
                    prev_q = q

                # Earliest: Before first buyback, add full cum
                if buyback_dates:
                    mask = data.index < buyback_dates[0]
                    if mask.any():
                        adjusted_shares.loc[mask] += cum_addback

                print(
                    f"Applied back-adjustments to shares for {ticker} (fallback mode)."
                )
            else:
                adjusted_shares = shares_daily  # No buybacks, no change

        fundamentals["AdjustedSharesOutstanding"] = adjusted_shares

        # ... (rest of the try block unchanged: divs, splits, recs, earnings_trend, earnings)
        divs = stock.dividends
        if not divs.empty:
            fundamentals = fundamentals.join(divs.rename("Dividends"), how="left")

        splits = stock.splits
        if not splits.empty:
            fundamentals = fundamentals.join(splits.rename("Splits"), how="left")

        try:
            recs = stock.recommendations
            if recs is not None and not recs.empty:
                recs_ffill = recs.reindex(data.index, method="ffill").ffill()
                fundamentals = fundamentals.join(recs_ffill, how="left")
                print(f"Fetched recommendations for {ticker}.")
        except Exception as rec_err:
            print(f"Recommendations error for {ticker}: {rec_err}")

        try:
            earnings_trend = stock.earnings_trend
            if earnings_trend is not None and not earnings_trend.empty:
                latest = earnings_trend.tail(1).to_dict("records")[0]
                for k, v in latest.items():
                    if ptypes.is_scalar(v) and (
                        not isinstance(v, str) or len(str(v)) < 150
                    ):
                        fundamentals[f"EarningsTrend_{k}"] = v
        except Exception as trend_err:
            print(f"Earnings trend error for {ticker}: {trend_err}")

        try:
            earnings = stock.earnings
            if not earnings.empty:
                earnings.index = pd.to_datetime(earnings.index.astype(str) + "-12-31")
                earnings_ffill = earnings.reindex(data.index, method="ffill").ffill()
                fundamentals = fundamentals.join(earnings_ffill, how="left")
                print(f"Fetched annual earnings for {ticker}.")
        except Exception as earn_err:
            print(f"Annual earnings error for {ticker}: {earn_err}")

    except Exception as e:
        print(f"Fundamentals error for {ticker}: {e}")

    merged = pd.concat([data, fundamentals], axis=1)

    for year, df_year in merged.groupby("Year"):
        df_year = df_year.drop(columns=["Year"], errors="ignore")
        file_path = f"{output_dir}/{ticker}_{year}.csv"
        df_year.to_csv(file_path, index=True)
        print(f"Saved {file_path}.")

print("Download complete.")
