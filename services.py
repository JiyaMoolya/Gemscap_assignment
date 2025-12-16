import pandas as pd
from database import load_bars
from ingestion import get_status

SYMBOLS = ["btcusdt", "ethusdt", "bnbusdt"]
TIMEFRAMES = ["1s", "1m", "5m"]

def _prepare_bars(df):
    if df.empty:
        return df
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").set_index("time")
    return df

def load_pair_bars(symbol_1, symbol_2, timeframe, lookback_hours=6):
    df1 = _prepare_bars(load_bars(timeframe, symbol_1, lookback_hours))
    df2 = _prepare_bars(load_bars(timeframe, symbol_2, lookback_hours))
    if df1.empty or df2.empty:
        return df1, df2

    # align on overlapping range
    min_len = min(len(df1), len(df2))
    if min_len == 0:
        return df1, df2
    df1 = df1.iloc[-min_len:]
    df2 = df2.iloc[-min_len:]
    return df1, df2

def health():
    return get_status()

