import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import time
import io
from datetime import datetime

from ingestion import start_stream
from services import load_pair_bars, health, SYMBOLS, TIMEFRAMES
from analytics import hedge_ratio, spread, zscore, rolling_corr, adf_test

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="Quant Analytics Dashboard",
    layout="wide"
)

st.title("📊 Real-Time Quant Analytics Dashboard")

# Store previous values for delta calculation
if 'prev_price1' not in st.session_state:
    st.session_state.prev_price1 = None
if 'prev_price2' not in st.session_state:
    st.session_state.prev_price2 = None
if 'prev_zscore' not in st.session_state:
    st.session_state.prev_zscore = None
if 'prev_corr' not in st.session_state:
    st.session_state.prev_corr = None

# ---------------- SIDEBAR CONTROLS ----------------
st.sidebar.header("Controls")

# Data Source Section
with st.sidebar.expander("📡 Data Source", expanded=True):
    data_mode = st.radio(
        "Data Source",
        ["Live Binance Data", "Uploaded OHLC Data"],
        label_visibility="collapsed"
    )

# Symbols & Timeframe Section
with st.sidebar.expander("📊 Symbols & Timeframe", expanded=True):
    symbol_1 = st.selectbox(
        "Select Symbol 1",
        SYMBOLS
    )
    
    symbol_2 = st.selectbox(
        "Select Symbol 2",
        SYMBOLS
    )
    
    timeframe = st.selectbox(
        "Resampling Timeframe",
        TIMEFRAMES
    )
    
    lookback_hours = st.slider(
        "Lookback (hours)",
        min_value=1,
        max_value=24,
        value=6
    )

# Analytics Parameters Section
with st.sidebar.expander("⚙️ Analytics Parameters", expanded=False):
    rolling_window = st.slider(
        "Rolling Window",
        min_value=5,
        max_value=100,
        value=20,
        help="Window size for rolling correlation calculation"
    )
    
    run_adf = st.button("Run ADF Test", use_container_width=True)

# Live Controls Section
with st.sidebar.expander("🔄 Live Controls", expanded=False):
    start_feed = st.button("▶ Start Live Feed", use_container_width=True)

# Initialize session state for auto-refresh
if 'auto_refresh_enabled' not in st.session_state:
    st.session_state.auto_refresh_enabled = False
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 3
if 'last_refresh_time' not in st.session_state:
    st.session_state.last_refresh_time = None

# Initialize session state for alert log
if 'alert_log' not in st.session_state:
    st.session_state.alert_log = []
if 'last_alert_state' not in st.session_state:
    st.session_state.last_alert_state = False  # Track if we were in alert state last time

# ---------------- AUTO-REFRESH CONTROLS (Live Mode Only) ----------------
if data_mode == "Live Binance Data":
    with st.sidebar.expander("🔄 Live Updates", expanded=False):
        auto_refresh = st.checkbox("Auto-refresh", value=st.session_state.auto_refresh_enabled)
        st.session_state.auto_refresh_enabled = auto_refresh
        
        if auto_refresh:
            refresh_interval = st.slider(
                "Refresh interval (seconds)",
                min_value=1,
                max_value=10,
                value=st.session_state.refresh_interval
            )
            st.session_state.refresh_interval = refresh_interval

# ---------------- DATA LOADING ----------------
if data_mode == "Live Binance Data":

    if start_feed:
        start_stream(symbol_1)
        start_stream(symbol_2)
        st.sidebar.success("Live feed started")

    time.sleep(1)
    df1_r, df2_r = load_pair_bars(symbol_1, symbol_2, timeframe, lookback_hours)
    
    # Update last refresh time
    st.session_state.last_refresh_time = datetime.now()

    status = health()
    last_update_str = st.session_state.last_refresh_time.strftime("%H:%M:%S") if st.session_state.last_refresh_time else "N/A"
    
    # Enhanced status strip with color coding
    status_container = st.container()
    with status_container:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            stream_status = "🟢 Active" if len(status['active_symbols']) > 0 else "🔴 Inactive"
            st.markdown(f"**Streams:** {stream_status}")
        with col2:
            st.markdown(f"**Queue:** {status['queue_size']}")
        with col3:
            flush_status = "🟢" if status['flush_alive'] else "🔴"
            st.markdown(f"**Flush:** {flush_status}")
        with col4:
            st.markdown(f"**Last update:** {last_update_str}")
        with col5:
            refresh_indicator = "🔄 Auto" if st.session_state.auto_refresh_enabled else "⏸️ Manual"
            st.markdown(f"**Mode:** {refresh_indicator}")

    if df1_r.empty or df2_r.empty or len(df1_r) < 2 or len(df2_r) < 2:
        st.info("Waiting for live resampled data...")
        st.stop()
    
    # Normalize: ensure 'price' column exists (map 'close' -> 'price' for bars)
    if 'price' not in df1_r.columns:
        if 'close' in df1_r.columns:
            df1_r['price'] = df1_r['close']
        else:
            st.error("Data missing required 'price' or 'close' column")
            st.stop()
    if 'price' not in df2_r.columns:
        if 'close' in df2_r.columns:
            df2_r['price'] = df2_r['close']
        else:
            st.error("Data missing required 'price' or 'close' column")
            st.stop()

else:
    # File uploader in sidebar
    with st.sidebar.expander("📁 Upload Data", expanded=True):
        uploaded_file = st.file_uploader(
            "Upload OHLC CSV",
            type=["csv"],
            label_visibility="visible"
        )

    if uploaded_file is None:
        st.info("Please upload an OHLC CSV file.")
        st.stop()

    ohlc = pd.read_csv(uploaded_file)
    ohlc["timestamp"] = pd.to_datetime(ohlc["timestamp"])
    ohlc.set_index("timestamp", inplace=True)

    # Normalize: ensure 'price' column exists
    if 'close' in ohlc.columns:
        ohlc = ohlc.rename(columns={"close": "price"})
    elif 'price' not in ohlc.columns:
        st.error("Uploaded CSV must contain 'close' or 'price' column")
        st.stop()
    df1_r = ohlc.copy()
    df2_r = df1_r.copy()  # For single-instrument analytics

# ---------------- ALIGN DATA ----------------
min_len = min(len(df1_r), len(df2_r))
df1_r = df1_r.iloc[-min_len:].reset_index(drop=True)
df2_r = df2_r.iloc[-min_len:].reset_index(drop=True)

if min_len < 2:
    st.info("Not enough overlapping resampled data to compute analytics. Waiting for more data...")
    st.stop()

# Defensive check: ensure 'price' column exists before analytics
if 'price' not in df1_r.columns or 'price' not in df2_r.columns:
    st.error("Data missing required 'price' column after processing")
    st.stop()

# ---------------- ANALYTICS ----------------
hedge = hedge_ratio(df1_r['price'], df2_r['price'])
spr = spread(df1_r['price'], df2_r['price'], hedge)
zs = zscore(spr)
corr = rolling_corr(df1_r['price'], df2_r['price'], rolling_window)

# Calculate deltas for metrics
current_price1 = df1_r['price'].iloc[-1]
current_price2 = df2_r['price'].iloc[-1]
current_z = zs.iloc[-1]
current_corr = corr.iloc[-1]

delta_price1 = current_price1 - st.session_state.prev_price1 if st.session_state.prev_price1 is not None else None
delta_price2 = current_price2 - st.session_state.prev_price2 if st.session_state.prev_price2 is not None else None
delta_z = current_z - st.session_state.prev_zscore if st.session_state.prev_zscore is not None else None
delta_corr = current_corr - st.session_state.prev_corr if st.session_state.prev_corr is not None else None

# Update session state for next iteration
st.session_state.prev_price1 = current_price1
st.session_state.prev_price2 = current_price2
st.session_state.prev_zscore = current_z
st.session_state.prev_corr = current_corr

# ---------------- HEADER INFO BAR ----------------
info_container = st.container()
with info_container:
    info_col1, info_col2, info_col3, info_col4 = st.columns(4)
    with info_col1:
        st.markdown(f"**Pair:** {symbol_1.upper()} / {symbol_2.upper()}")
    with info_col2:
        st.markdown(f"**Timeframe:** {timeframe}")
    with info_col3:
        st.markdown(f"**Lookback:** {lookback_hours}h")
    with info_col4:
        data_points = min(len(df1_r), len(df2_r))
        st.markdown(f"**Data Points:** {data_points}")
st.divider()

# ---------------- TABS ----------------
tab_prices, tab_analytics, tab_alerts, tab_upload = st.tabs(
    ["📈 Prices", "📊 Analytics", "🚨 Alerts", "📂 OHLC Upload"]
)

# ================= TAB: PRICES =================
with tab_prices:
    # Create figure with dual y-axes
    fig_price = go.Figure()
    
    # Add trace for symbol 1 (left y-axis)
    fig_price.add_trace(go.Scatter(
        x=df1_r.index,
        y=df1_r['price'],
        name=f"{symbol_1.upper()}",
        line=dict(color='#1f77b4', width=2),
        hovertemplate='<b>%{fullData.name}</b><br>' +
                      'Index: %{x}<br>' +
                      'Price: $%{y:.2f}<br>' +
                      '<extra></extra>'
    ))
    
    # Add trace for symbol 2 (right y-axis)
    fig_price.add_trace(go.Scatter(
        x=df2_r.index,
        y=df2_r['price'],
        name=f"{symbol_2.upper()}",
        line=dict(color='#ff7f0e', width=2),
        yaxis='y2',
        hovertemplate='<b>%{fullData.name}</b><br>' +
                      'Index: %{x}<br>' +
                      'Price: $%{y:.2f}<br>' +
                      '<extra></extra>'
    ))
    
    # Add vertical line at latest timestamp
    max_idx = max(df1_r.index.max(), df2_r.index.max()) if len(df1_r) > 0 and len(df2_r) > 0 else 0
    fig_price.add_vline(
        x=max_idx,
        line_dash="dot",
        line_color="gray",
        opacity=0.5,
        annotation_text="Latest"
    )
    
    # Update layout with dual y-axes
    fig_price.update_layout(
        title=f"Price Comparison: {symbol_1.upper()} vs {symbol_2.upper()}",
        xaxis_title="Index",
        yaxis=dict(
            title=dict(text=f"{symbol_1.upper()} Price", font=dict(color='#1f77b4')),
            tickfont=dict(color='#1f77b4')
        ),
        yaxis2=dict(
            title=dict(text=f"{symbol_2.upper()} Price", font=dict(color='#ff7f0e')),
            tickfont=dict(color='#ff7f0e'),
            anchor="x",
            overlaying="y",
            side="right"
        ),
        hovermode="x unified",
        template="plotly_white",
        height=500,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_price, use_container_width=True)

# ================= TAB: ANALYTICS =================
with tab_analytics:
    # Color-coded metrics with deltas
    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        delta_str1 = f"{delta_price1:+.2f}" if delta_price1 is not None else None
        st.metric(
            label=f"{symbol_1.upper()} Price",
            value=f"${current_price1:.2f}",
            delta=delta_str1
        )
    
    with c2:
        delta_str2 = f"{delta_price2:+.2f}" if delta_price2 is not None else None
        st.metric(
            label=f"{symbol_2.upper()} Price",
            value=f"${current_price2:.2f}",
            delta=delta_str2
        )
    
    with c3:
        # Color code z-score: red if > threshold, yellow if > 1, green otherwise
        z_val = current_z
        if abs(z_val) > 2:
            delta_color = "inverse"  # Red for high z-score
        elif abs(z_val) > 1:
            delta_color = "off"  # Yellow/warning
        else:
            delta_color = "normal"  # Green
        
        delta_str_z = f"{delta_z:+.2f}" if delta_z is not None else None
        st.metric(
            label="Z-Score",
            value=f"{z_val:.2f}",
            delta=delta_str_z,
            delta_color=delta_color
        )
    
    with c4:
        delta_str_corr = f"{delta_corr:+.3f}" if delta_corr is not None else None
        st.metric(
            label="Rolling Correlation",
            value=f"{current_corr:.3f}",
            delta=delta_str_corr
        )

    st.subheader("Spread")
    fig_spread = go.Figure()
    fig_spread.add_trace(go.Scatter(
        x=spr.index,
        y=spr,
        name="Spread",
        line=dict(color='#2ca02c', width=2),
        fill='tozeroy',
        fillcolor='rgba(44, 160, 44, 0.1)',
        hovertemplate='<b>Spread</b><br>' +
                      'Index: %{x}<br>' +
                      'Spread: %{y:.4f}<br>' +
                      '<extra></extra>'
    ))
    # Add zero reference line
    fig_spread.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray",
        opacity=0.5,
        annotation_text="Zero"
    )
    # Add annotation for current spread
    if len(spr) > 0:
        current_spread = spr.iloc[-1]
        mean_spread = spr.mean()
        fig_spread.add_annotation(
            x=spr.index[-1],
            y=current_spread,
            text=f"Current: {current_spread:.4f}<br>Mean: {mean_spread:.4f}",
            showarrow=True,
            arrowhead=2,
            bgcolor="rgba(255,255,255,0.8)"
        )
    fig_spread.update_layout(
        xaxis_title="Index",
        yaxis_title="Spread",
        hovermode="x unified",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_spread, use_container_width=True)

    st.subheader("Z-Score")
    fig_z = go.Figure()
    
    # Add z-score line
    fig_z.add_trace(go.Scatter(
        x=zs.index,
        y=zs,
        name="Z-Score",
        line=dict(color='#9467bd', width=2),
        hovertemplate='<b>Z-Score</b><br>' +
                      'Index: %{x}<br>' +
                      'Z-Score: %{y:.2f}<br>' +
                      '<extra></extra>'
    ))
    
    # Add threshold lines and shaded regions
    fig_z.add_hline(y=2, line_dash="dash", line_color="red", line_width=2, annotation_text="+2σ")
    fig_z.add_hline(y=-2, line_dash="dash", line_color="red", line_width=2, annotation_text="-2σ")
    fig_z.add_hline(y=1, line_dash="dot", line_color="orange", line_width=1, opacity=0.7, annotation_text="+1σ")
    fig_z.add_hline(y=-1, line_dash="dot", line_color="orange", line_width=1, opacity=0.7, annotation_text="-1σ")
    
    # Add shaded regions
    fig_z.add_hrect(y0=2, y1=10, fillcolor="red", opacity=0.1, layer="below", line_width=0)
    fig_z.add_hrect(y0=1, y1=2, fillcolor="orange", opacity=0.1, layer="below", line_width=0)
    fig_z.add_hrect(y0=-1, y1=1, fillcolor="green", opacity=0.1, layer="below", line_width=0)
    fig_z.add_hrect(y0=-2, y1=-1, fillcolor="orange", opacity=0.1, layer="below", line_width=0)
    fig_z.add_hrect(y0=-10, y1=-2, fillcolor="red", opacity=0.1, layer="below", line_width=0)
    
    # Add annotation for current z-score
    if len(zs) > 0:
        current_z_val = zs.iloc[-1]
        interpretation = "Extreme" if abs(current_z_val) > 2 else "Warning" if abs(current_z_val) > 1 else "Normal"
        fig_z.add_annotation(
            x=zs.index[-1],
            y=current_z_val,
            text=f"Current: {current_z_val:.2f}<br>{interpretation}",
            showarrow=True,
            arrowhead=2,
            bgcolor="rgba(255,255,255,0.8)"
        )
    
    fig_z.update_layout(
        xaxis_title="Index",
        yaxis_title="Z-Score",
        hovermode="x unified",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_z, use_container_width=True)

    st.subheader("Rolling Correlation")
    fig_corr = go.Figure()
    fig_corr.add_trace(go.Scatter(
        x=corr.index,
        y=corr,
        name="Correlation",
        line=dict(color='#17becf', width=2),
        hovertemplate='<b>Rolling Correlation</b><br>' +
                      'Index: %{x}<br>' +
                      'Correlation: %{y:.3f}<br>' +
                      f'Window: {rolling_window}<br>' +
                      '<extra></extra>'
    ))
    
    # Add reference lines
    fig_corr.add_hline(y=0.8, line_dash="dash", line_color="green", line_width=1, opacity=0.7, annotation_text="Strong (0.8)")
    fig_corr.add_hline(y=0.5, line_dash="dot", line_color="orange", line_width=1, opacity=0.7, annotation_text="Moderate (0.5)")
    
    # Add shaded regions
    fig_corr.add_hrect(y0=0.8, y1=1.0, fillcolor="green", opacity=0.1, layer="below", line_width=0)
    fig_corr.add_hrect(y0=0.5, y1=0.8, fillcolor="orange", opacity=0.1, layer="below", line_width=0)
    fig_corr.add_hrect(y0=0.0, y1=0.5, fillcolor="red", opacity=0.1, layer="below", line_width=0)
    
    # Add annotation for current correlation
    if len(corr) > 0:
        current_corr_val = corr.iloc[-1]
        if current_corr_val > 0.8:
            interpretation = "Strong"
        elif current_corr_val > 0.5:
            interpretation = "Moderate"
        else:
            interpretation = "Weak"
        fig_corr.add_annotation(
            x=corr.index[-1],
            y=current_corr_val,
            text=f"Current: {current_corr_val:.3f}<br>{interpretation}",
            showarrow=True,
            arrowhead=2,
            bgcolor="rgba(255,255,255,0.8)"
        )
    
    fig_corr.update_layout(
        xaxis_title="Index",
        yaxis_title="Rolling Correlation",
        yaxis_range=[-0.1, 1.1],
        hovermode="x unified",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_corr, use_container_width=True)

    if run_adf:
        st.divider()
        st.subheader("Augmented Dickey-Fuller (ADF) Test")
        stat, pval = adf_test(spr)
        
        # Format ADF results as a card
        adf_container = st.container()
        with adf_container:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("ADF Statistic", f"{stat:.4f}")
            with col2:
                # Color code based on significance
                significance_level = 0.05
                if pval < significance_level:
                    pval_color = "🟢"
                    interpretation = "Stationary"
                    interpretation_color = "green"
                else:
                    pval_color = "🔴"
                    interpretation = "Non-Stationary"
                    interpretation_color = "red"
                
                st.metric(
                    "p-value",
                    f"{pval:.4f}",
                    delta=f"{pval_color} {interpretation}",
                    delta_color=interpretation_color
                )
            
            # Interpretation and explanation
            st.info(
                f"**Interpretation:** The spread is **{interpretation.lower()}** "
                f"(p-value: {pval:.4f}). "
                f"A p-value < 0.05 suggests the spread is mean-reverting, "
                f"which is favorable for pairs trading strategies."
            )
            
            st.caption(
                "💡 **Note:** The ADF test checks for stationarity (mean-reversion). "
                "A stationary spread indicates the pair relationship is stable over time."
            )

    # Prepare export data
    export_df = pd.DataFrame({
        "price_1": df1_r['price'],
        "price_2": df2_r['price'],
        "spread": spr,
        "z_score": zs,
        "correlation": corr
    })
    
    # Generate filename with metadata
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"analytics_{symbol_1}_{symbol_2}_{timeframe}_{timestamp_str}"
    
    # Export options
    st.subheader("Export Data")
    export_col1, export_col2, export_col3 = st.columns(3)
    
    with export_col1:
        csv_data = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download CSV",
            csv_data,
            f"{base_filename}.csv",
            "text/csv",
            use_container_width=True
        )
    
    with export_col2:
        json_data = export_df.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button(
            "📥 Download JSON",
            json_data,
            f"{base_filename}.json",
            "application/json",
            use_container_width=True
        )
    
    with export_col3:
        try:
            # Try Excel export (requires openpyxl)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='Analytics')
            excel_data = excel_buffer.getvalue()
            st.download_button(
                "📥 Download Excel",
                excel_data,
                f"{base_filename}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except ImportError:
            st.info("💡 Excel export requires 'openpyxl'. Install with: `pip install openpyxl`")
            st.download_button(
                "📥 Download Excel (disabled)",
                b"",
                f"{base_filename}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                disabled=True
            )
        except Exception as e:
            st.warning(f"Excel export unavailable: {str(e)}")
            st.download_button(
                "📥 Download Excel (disabled)",
                b"",
                f"{base_filename}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                disabled=True
            )

# ================= TAB: ALERTS =================
with tab_alerts:
    # Threshold control
    col_thresh1, col_thresh2 = st.columns([2, 1])
    with col_thresh1:
        threshold = st.number_input("Z-Score Threshold", value=2.0, min_value=0.0, max_value=5.0, step=0.1)
    with col_thresh2:
        st.write("")  # Spacing
        st.write("")  # Spacing
    
    current_z = zs.iloc[-1]
    current_alert_state = abs(current_z) > threshold
    
    # Check for new alert (only log when crossing threshold, not when staying above)
    if current_alert_state and not st.session_state.last_alert_state:
        # Just crossed into alert state - log it
        alert_type = "Upper" if current_z > threshold else "Lower"
        alert_entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "z_score": current_z,
            "type": alert_type,
            "threshold": threshold
        }
        st.session_state.alert_log.append(alert_entry)
    
    # Update alert state for next iteration
    st.session_state.last_alert_state = current_alert_state
    
    # Visual gauge/indicator
    st.subheader("Current Z-Score Status")
    
    # Create a visual gauge using columns and color coding
    gauge_col1, gauge_col2, gauge_col3 = st.columns([1, 2, 1])
    with gauge_col2:
        # Determine color and status
        if abs(current_z) > threshold:
            status_color = "🔴"
            status_text = "ALERT TRIGGERED"
            status_bg = "background-color: #fee; padding: 10px; border-radius: 5px; text-align: center;"
        elif abs(current_z) > threshold * 0.7:  # Warning zone (70% of threshold)
            status_color = "🟡"
            status_text = "WARNING ZONE"
            status_bg = "background-color: #ffe; padding: 10px; border-radius: 5px; text-align: center;"
        else:
            status_color = "🟢"
            status_text = "NORMAL"
            status_bg = "background-color: #efe; padding: 10px; border-radius: 5px; text-align: center;"
        
        st.markdown(
            f'<div style="{status_bg}">'
            f'<h3>{status_color} {status_text}</h3>'
            f'<p style="font-size: 24px; font-weight: bold;">Z-Score: {current_z:.2f}</p>'
            f'<p>Threshold: ±{threshold:.1f}</p>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    # Z-Score history chart with threshold bands
    st.subheader("Z-Score History")
    fig_alert_z = go.Figure()
    
    # Add z-score line
    fig_alert_z.add_trace(go.Scatter(
        x=zs.index,
        y=zs,
        name="Z-Score",
        line=dict(color='#9467bd', width=2),
        hovertemplate='<b>Z-Score</b><br>' +
                      'Index: %{x}<br>' +
                      'Z-Score: %{y:.2f}<br>' +
                      '<extra></extra>'
    ))
    
    # Add threshold bands
    fig_alert_z.add_hline(y=threshold, line_dash="dash", line_color="red", line_width=2, 
                          annotation_text=f"+{threshold:.1f}σ", annotation_position="right")
    fig_alert_z.add_hline(y=-threshold, line_dash="dash", line_color="red", line_width=2,
                          annotation_text=f"-{threshold:.1f}σ", annotation_position="right")
    fig_alert_z.add_hline(y=threshold * 0.7, line_dash="dot", line_color="orange", line_width=1,
                          opacity=0.7, annotation_text=f"Warning +{threshold * 0.7:.1f}σ")
    fig_alert_z.add_hline(y=-threshold * 0.7, line_dash="dot", line_color="orange", line_width=1,
                          opacity=0.7, annotation_text=f"Warning -{threshold * 0.7:.1f}σ")
    
    # Add shaded regions
    fig_alert_z.add_hrect(y0=threshold, y1=10, fillcolor="red", opacity=0.15, layer="below", line_width=0)
    fig_alert_z.add_hrect(y0=-threshold, y1=-10, fillcolor="red", opacity=0.15, layer="below", line_width=0)
    fig_alert_z.add_hrect(y0=threshold * 0.7, y1=threshold, fillcolor="orange", opacity=0.1, layer="below", line_width=0)
    fig_alert_z.add_hrect(y0=-threshold, y1=-threshold * 0.7, fillcolor="orange", opacity=0.1, layer="below", line_width=0)
    fig_alert_z.add_hrect(y0=-threshold * 0.7, y1=threshold * 0.7, fillcolor="green", opacity=0.1, layer="below", line_width=0)
    
    # Highlight current value
    if len(zs) > 0:
        fig_alert_z.add_annotation(
            x=zs.index[-1],
            y=current_z,
            text=f"Current: {current_z:.2f}",
            showarrow=True,
            arrowhead=2,
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="black",
            borderwidth=1
        )
    
    fig_alert_z.update_layout(
        xaxis_title="Index",
        yaxis_title="Z-Score",
        hovermode="x unified",
        template="plotly_white",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig_alert_z, use_container_width=True)
    
    # Alert log
    st.subheader(f"Alert Log ({len(st.session_state.alert_log)} alerts)")
    
    if len(st.session_state.alert_log) > 0:
        # Show recent alerts (last 10)
        recent_alerts = st.session_state.alert_log[-10:]
        recent_alerts.reverse()  # Show most recent first
        
        for alert in recent_alerts:
            alert_color = "🔴" if alert["type"] == "Upper" else "🔵"
            st.markdown(
                f"{alert_color} **{alert['timestamp']}** | "
                f"Z-Score: **{alert['z_score']:.2f}** | "
                f"Type: **{alert['type']} breach** (threshold: ±{alert['threshold']:.1f})"
            )
        
        # Clear log button
        if st.button("Clear Alert Log", use_container_width=True):
            st.session_state.alert_log = []
            st.rerun()
    else:
        st.info("No alerts triggered yet. Alerts will appear here when z-score exceeds the threshold.")

# ================= TAB: UPLOAD INFO =================
with tab_upload:
    st.markdown("""
    **Supported CSV Format**

    Required columns:
    - timestamp
    - open
    - high
    - low
    - close

    Uploaded OHLC data is treated as a first-class data source and passed through
    the same analytics pipeline as live market data.
    """)

# ---------------- AUTO-REFRESH HANDLING (Live Mode Only) ----------------
if data_mode == "Live Binance Data" and st.session_state.auto_refresh_enabled:
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
