import yfinance as yf
from bs4 import BeautifulSoup
import pandas as pd


def main():
    path_to_outputs = "/outputs/"
    sp_data = "./datasets/sp_data.csv"

    df = pd.read_csv(sp_data)
    print(df.head())


if __name__ == "__main__":
    main()
