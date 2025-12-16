import sqlite3
import pandas as pd

DB_NAME = "market_data.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

BAR_TABLES = {
    "1s": "bars_1s",
    "1m": "bars_1m",
    "5m": "bars_5m",
}

def create_table():
    create_tables()

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ticks (
            time TEXT,
            symbol TEXT,
            price REAL,
            qty REAL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time ON ticks(symbol, time)")
    for tbl in BAR_TABLES.values():
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {tbl} (
                time TEXT,
                symbol TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                UNIQUE(symbol, time)
            )
        """)
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_symbol_time ON {tbl}(symbol, time)")
    conn.commit()
    conn.close()

def insert_tick(time, symbol, price, qty):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ticks VALUES (?, ?, ?, ?)",
        (time, symbol, price, qty)
    )
    conn.commit()
    conn.close()

def insert_or_replace_bars(table_name, bars):
    if not bars:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        f"""
        INSERT INTO {table_name} (time, symbol, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, time) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume
        """,
        [
            (
                b["time"],
                b["symbol"],
                b["open"],
                b["high"],
                b["low"],
                b["close"],
                b["volume"],
            )
            for b in bars
        ]
    )
    conn.commit()
    conn.close()

def insert_ticks_bulk(ticks):
    if not ticks:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO ticks (time, symbol, price, qty) VALUES (?, ?, ?, ?)",
        [(t["time"], t["symbol"], t["price"], t["qty"]) for t in ticks]
    )
    conn.commit()
    conn.close()

def prune_ticks_older_than(hours):
    if hours is None:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM ticks WHERE time < datetime('now', ?)",
        (f"-{int(hours)} hours",)
    )
    conn.commit()
    conn.close()

def load_ticks(symbol=None, since=None, limit=None):
    # Ensure tables exist before attempting to read
    create_tables()
    conn = get_connection()
    query = "SELECT * FROM ticks"
    clauses = []
    params = []
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol)
    if since:
        clauses.append("time >= ?")
        params.append(since)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY time ASC"
    if limit:
        query += f" LIMIT {int(limit)}"
    try:
        df = pd.read_sql(query, conn, params=params)
    except Exception:
        conn.close()
        return pd.DataFrame(columns=["time", "symbol", "price", "qty"])
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return df

def load_bars(timeframe, symbol=None, lookback=None):
    table = BAR_TABLES.get(timeframe)
    if not table:
        return pd.DataFrame(columns=["time", "symbol", "open", "high", "low", "close", "volume"])
    create_tables()
    conn = get_connection()
    query = f"SELECT * FROM {table}"
    clauses = []
    params = []
    if symbol:
        clauses.append("symbol = ?")
        params.append(symbol)
    if lookback:
        clauses.append("time >= datetime('now', ?)")
        params.append(f"-{int(lookback)} hours")
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY time ASC"
    try:
        df = pd.read_sql(query, conn, params=params)
    except Exception:
        conn.close()
        return pd.DataFrame(columns=["time", "symbol", "open", "high", "low", "close", "volume"])
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return df
