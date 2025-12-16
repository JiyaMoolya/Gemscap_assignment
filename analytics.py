import pandas as pd
import numpy as np
from statsmodels.api import OLS, add_constant
from statsmodels.tsa.stattools import adfuller

def prepare_dataframe(df):
    df["time"] = pd.to_datetime(df["time"])
    df.set_index("time", inplace=True)
    return df

def resample(df, timeframe):
    rule = {"1s": "1S", "1m": "1T", "5m": "5T"}[timeframe]
    return df.resample(rule).agg({
        "price": "last",
        "qty": "sum"
    }).dropna()

def hedge_ratio(y, x):
    # Convert inputs to numpy arrays to avoid pandas Index alignment issues
    y_arr = np.asarray(y).astype(float)
    x_arr = np.asarray(x).astype(float)

    # Ensure 1-D
    if y_arr.ndim != 1:
        y_arr = y_arr.ravel()
    if x_arr.ndim != 1:
        x_arr = x_arr.ravel()

    # Trim to the same (last) length if needed
    min_len = min(len(y_arr), len(x_arr))
    if min_len == 0:
        raise ValueError("Not enough data to compute hedge ratio")
    y_arr = y_arr[-min_len:]
    x_arr = x_arr[-min_len:]

    x_with_const = add_constant(x_arr)
    model = OLS(y_arr, x_with_const).fit()
    return model.params[1]

def spread(series1, series2, hedge):
    return series1 - hedge * series2

def zscore(series):
    return (series - series.mean()) / series.std()

def rolling_corr(s1, s2, window):
    return s1.rolling(window).corr(s2)

def adf_test(series):
    stat, pval, *_ = adfuller(series.dropna())
    return stat, pval
