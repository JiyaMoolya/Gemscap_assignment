# Real-Time Quant Analytics Dashboard

A professional end-to-end quantitative trading analytics system with real-time Binance WebSocket data ingestion, advanced statistical analysis, and an interactive Streamlit dashboard.

## 🎯 Features

### Real-Time Data Ingestion
- **Binance WebSocket Integration**: Live tick data from Binance Futures
- **Robust Connection Handling**: Automatic reconnection with exponential backoff
- **Batch Processing**: Efficient tick batching and database writes
- **Data Retention**: Configurable retention policies

### Data Storage & Resampling
- **SQLite Database**: Persistent storage for tick data
- **OHLCV Bar Generation**: Automatic resampling to 1s, 1m, and 5m timeframes
- **Incremental Updates**: Efficient bar aggregation and storage
- **Indexed Queries**: Fast data retrieval with proper indexing

### Quantitative Analytics
- **Hedge Ratio Calculation**: OLS regression-based hedge ratio
- **Spread Analysis**: Price spread computation and visualization
- **Z-Score Calculation**: Statistical normalization for mean reversion strategies
- **Rolling Correlation**: Dynamic correlation analysis with configurable windows
- **ADF Test**: Augmented Dickey-Fuller test for stationarity (mean-reversion)

### Interactive Dashboard
- **Live Updates**: Auto-refresh with configurable intervals
- **Multi-Timeframe Support**: 1s, 1m, and 5m resampling
- **Professional Visualizations**: 
  - Dual y-axis price charts
  - Color-coded spread analysis
  - Z-score with threshold bands
  - Rolling correlation with interpretation zones
- **Alert System**: Real-time z-score threshold alerts with session log
- **Data Export**: CSV, JSON, and Excel formats with metadata

## 📋 Requirements

- Python 3.8+
- See `requirement.txt` for full dependency list

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/JiyaMoolya/Gemscap_assignment.git
   cd Gemscap_assignment
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**
   - Windows:
     ```bash
     venv\Scripts\activate
     ```
   - Linux/Mac:
     ```bash
     source venv/bin/activate
     ```

4. **Install dependencies**
   ```bash
   pip install -r requirement.txt
   ```

5. **Optional: Install openpyxl for Excel export**
   ```bash
   pip install openpyxl
   ```

## 🏃 Running the Application

1. **Start the Streamlit dashboard**
   ```bash
   streamlit run app.py
   ```

2. **Access the dashboard**
   - Open your browser to `http://localhost:8501`

3. **Start live data feed**
   - Select symbols and timeframe in the sidebar
   - Click "▶ Start Live Feed" to begin data ingestion
   - Enable auto-refresh for real-time updates

## 📁 Project Structure

```
.
├── app.py              # Main Streamlit dashboard application
├── ingestion.py        # WebSocket data ingestion and processing
├── database.py         # SQLite database operations
├── analytics.py        # Quantitative analytics functions
├── services.py         # Service layer for data loading and health
├── requirement.txt     # Python dependencies
├── README.md          # This file
└── .gitignore         # Git ignore rules
```

## 🔧 Architecture

### Components

- **Ingestion Layer** (`ingestion.py`): WebSocket connection management, tick buffering, and batch processing
- **Storage Layer** (`database.py`): SQLite operations, bar aggregation, and data persistence
- **Analytics Layer** (`analytics.py`): Statistical calculations (hedge ratio, spread, z-score, correlation, ADF)
- **Service Layer** (`services.py`): Data loading, alignment, and health monitoring
- **UI Layer** (`app.py`): Streamlit dashboard with interactive visualizations

### Data Flow

1. **Ingestion**: Binance WebSocket → Tick Buffer → Batch Insert → Database
2. **Aggregation**: Ticks → OHLCV Bars (1s/1m/5m) → Bar Tables
3. **Analytics**: Load Bars → Align Data → Compute Metrics → Visualize
4. **UI**: User Interactions → Data Refresh → Chart Updates

## 📊 Usage Guide

### Live Data Mode

1. Select two trading pairs (e.g., BTCUSDT, ETHUSDT)
2. Choose a timeframe (1s, 1m, or 5m)
3. Set lookback period (hours)
4. Click "Start Live Feed" to begin ingestion
5. Enable auto-refresh for continuous updates

### Uploaded Data Mode

1. Prepare a CSV file with columns: `timestamp`, `open`, `high`, `low`, `close`
2. Select "Uploaded OHLC Data" mode
3. Upload your CSV file
4. Analytics will be computed on the uploaded data

### Analytics Features

- **Hedge Ratio**: OLS-based hedge ratio for pairs trading
- **Spread**: Price difference between the two instruments
- **Z-Score**: Normalized spread for mean reversion signals
- **Rolling Correlation**: Dynamic correlation with configurable window
- **ADF Test**: Stationarity test (click "Run ADF Test" button)

### Alerts

- Set z-score threshold in the Alerts tab
- Visual gauge shows current status (Normal/Warning/Alert)
- Alert log tracks threshold breaches with timestamps
- Color-coded zones for quick interpretation

### Export

- Export analytics data in CSV, JSON, or Excel formats
- Filenames include metadata: `analytics_{symbol1}_{symbol2}_{timeframe}_{timestamp}`
- All exports reflect the currently displayed data

## 🛠️ Configuration

### Supported Symbols
- BTCUSDT
- ETHUSDT
- BNBUSDT

### Timeframes
- 1s (1 second)
- 1m (1 minute)
- 5m (5 minutes)

### Default Settings
- Lookback: 6 hours
- Rolling Window: 20 periods
- Auto-refresh Interval: 3 seconds (when enabled)

## 📝 Notes

- The database file (`market_data.db`) is created automatically
- Data retention is set to 6 hours by default (configurable in code)
- Excel export requires `openpyxl` package (optional)
- WebSocket connections automatically reconnect on failure

## 🔒 Data Privacy

- All data is stored locally in SQLite database
- No data is sent to external servers (except Binance WebSocket)
- Database file can be deleted to clear all stored data

## 📄 License

This project is part of a quantitative developer evaluation assignment.

## 👤 Author

JiyaMoolya

## 🙏 Acknowledgments

- Binance for WebSocket API
- Streamlit for the dashboard framework
- Plotly for interactive visualizations
- Statsmodels for statistical analysis

