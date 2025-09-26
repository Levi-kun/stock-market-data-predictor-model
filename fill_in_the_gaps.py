import pandas as pd
import yfinance as yf
from pandas_datareader import data as pdr
from datetime import datetime
import warnings

warnings.filterwarnings("ignore")

current_data = "datasets/sp_data.csv"
