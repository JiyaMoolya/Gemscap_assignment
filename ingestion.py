import json
import threading
import time
import queue
import websocket
import pandas as pd
from datetime import datetime, timezone
from database import (
    create_tables,
    insert_ticks_bulk,
    insert_or_replace_bars,
    prune_ticks_older_than,
    BAR_TABLES,
)

_tick_queue = queue.Queue(maxsize=10_000)
_flush_thread = None
_stream_threads = {}
_stop_flags = {}

def _on_message(ws, message):
    data = json.loads(message)
    tick = {
        "time": datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc).isoformat(),
        "symbol": data["s"].lower(),
        "price": float(data["p"]),
        "qty": float(data["q"])
    }
    try:
        _tick_queue.put_nowait(tick)
    except queue.Full:
        # Drop oldest if queue is full to keep moving
        try:
            _tick_queue.get_nowait()
            _tick_queue.put_nowait(tick)
        except queue.Empty:
            pass

def _start_socket(symbol, stop_event):
    url = f"wss://fstream.binance.com/ws/{symbol}@trade"
    backoff = 1
    while not stop_event.is_set():
        try:
            ws = websocket.WebSocketApp(
                url,
                on_message=_on_message,
                on_error=lambda ws, err: None,
                on_close=lambda ws, *args: None,
            )
            ws.run_forever(ping_interval=20, ping_timeout=10)
            backoff = min(backoff * 2, 30)
        except Exception:
            backoff = min(backoff * 2, 30)
        time.sleep(backoff)

def _ensure_flush_thread(batch_size=200, flush_interval=1.0, retention_hours=6):
    global _flush_thread
    if _flush_thread and _flush_thread.is_alive():
        return

    def _flush_loop():
        create_tables()
        last_prune = time.time()
        while True:
            batch = []
            start = time.time()
            while len(batch) < batch_size and time.time() - start < flush_interval:
                try:
                    item = _tick_queue.get(timeout=flush_interval)
                    batch.append(item)
                except queue.Empty:
                    break
            if batch:
                insert_ticks_bulk(batch)
                _aggregate_and_store_bars(batch)
            if retention_hours and time.time() - last_prune > 300:
                prune_ticks_older_than(retention_hours)
                last_prune = time.time()

    _flush_thread = threading.Thread(target=_flush_loop, daemon=True)
    _flush_thread.start()

def _aggregate_and_store_bars(batch):
    if not batch:
        return
    df = pd.DataFrame(batch)
    if df.empty:
        return
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df.set_index("time", inplace=True)
    rules = {"1s": "1S", "1m": "1T", "5m": "5T"}
    for tf, rule in rules.items():
        table = BAR_TABLES[tf]
        grouped = (
            df.groupby("symbol")
              .resample(rule)
              .agg(
                  open=("price", "first"),
                  high=("price", "max"),
                  low=("price", "min"),
                  close=("price", "last"),
                  volume=("qty", "sum"),
              )
              .dropna()
        )
        if grouped.empty:
            continue
        grouped = grouped.reset_index()
        records = grouped.to_dict("records")
        bars = []
        for rec in records:
            bars.append(
                {
                    "time": rec["time"].isoformat(),
                    "symbol": rec["symbol"],
                    "open": rec["open"],
                    "high": rec["high"],
                    "low": rec["low"],
                    "close": rec["close"],
                    "volume": rec["volume"],
                }
            )
        insert_or_replace_bars(table, bars)

def start_stream(symbol):
    if symbol in _stream_threads:
        return
    create_tables()
    _ensure_flush_thread()
    stop_event = threading.Event()
    thread = threading.Thread(target=_start_socket, args=(symbol, stop_event), daemon=True)
    _stream_threads[symbol] = thread
    _stop_flags[symbol] = stop_event
    thread.start()

def stop_stream(symbol):
    if symbol not in _stream_threads:
        return
    _stop_flags[symbol].set()
    _stream_threads.pop(symbol, None)
    _stop_flags.pop(symbol, None)

def get_status():
    return {
        "active_symbols": list(_stream_threads.keys()),
        "queue_size": _tick_queue.qsize(),
        "flush_alive": _flush_thread.is_alive() if _flush_thread else False,
    }
