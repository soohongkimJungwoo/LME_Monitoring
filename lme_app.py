import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime

# --- 기본 설정 ---
st.set_page_config(page_title="LME 글로벌 모니터링 시스템", layout="wide")


# --- 1. 환율 가져오기 (야후 파이낸스) ---
@st.cache_data(ttl=3600)
def fetch_exchange_rate():
    try:
        krw = yf.Ticker("KRW=X")
        hist = krw.history(period="3d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        return 1450.0
    except:
        return 1450.0


# --- 2. LME 데이터 수집 및 가공 ---
@st.cache_data(ttl=3600)
def fetch_global_lme(rate):
    tickers = {
        "Cu(구리)": "HG=F",
        "Al(알루미늄)": "ALI=F",
        "Zn(아연)": "ZNC=F",
        "Pb(납)": "LEAD=F",
        "Ni(니켈)": "NI=F",
        "Sn(주석)": "TIN=F"
    }

    combined_data = []
    for name, ticker in tickers.items():
        try:
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if not data.empty:
                temp_df = data[['Close']].reset_index()
                temp_df.columns = ['날짜', name]
                combined_data.append(temp_df.set_index('날짜'))
        except:
            continue

    if not combined_data: return None

    df = pd.concat(combined_data, axis=1).sort_index(ascending=False).reset_index()
    df = df.fillna(method='ffill').fillna(method='bfill')

    for name in tickers.keys():
        if name in df.columns:
            if name == "Cu(구리)":
                df[name] = df[name] * 2204.62
                # 원화 환산 컬럼 미리 생성
            df[f"{name}_KRW"] = df[name] * rate

    return df


# --- UI 레이아웃 ---
st.title("📊 LME 비철금속 모니터링 시스템")

exchange_rate = fetch_exchange_rate()
df = fetch_global_lme(exchange_rate)

# --- 사이드바 설정 (통화 선택 추가) ---
st.sidebar.header("⚙️ 표시 설정")
currency = st.sidebar.radio("💰 표시 통화 선택", ["원화 (KRW)", "달러 (USD)"])
currency_suffix = "원" if currency == "원화 (KRW)" else "$"
currency_col_suffix = "_KRW" if currency == "원화 (KRW)" else ""

st.sidebar.divider()
st.sidebar.success(f"**현재 기준 환율:** {exchange_rate:,.2f} 원/달러")

if df is not None and not df.empty:
    # 1. 상단 요약
    latest = df.iloc[0]
    st.subheader(f"📅 데이터 기준일: {latest['날짜'].strftime('%Y-%m-%d')}")

    m1, m2, m3 = st.columns(3)
    items = ['Cu(구리)', 'Al(알루미늄)', 'Zn(아연)']
    for i, item in enumerate(items):
        col_name = f"{item}{currency_col_suffix}"
        if col_name in df.columns:
            curr = latest[col_name]
            prev = df.iloc[1][col_name] if len(df) > 1 else curr

            value_fmt = f"{int(curr):,}{currency_suffix}" if currency == "원화 (KRW)" else f"${curr:,.1f}"
            delta_fmt = f"{int(curr - prev):,}{currency_suffix}" if currency == "원화 (KRW)" else f"${curr - prev:,.1f}"

            [m1, m2, m3][i].metric(label=f"{item} ({currency})", value=value_fmt, delta=delta_fmt)

    st.divider()

    # 2. 메인 분석 탭
    tab1, tab2 = st.tabs(["📈 일별 시세 추이", "📈 월별 평균 분석"])

    # 공통 그래프 폰트 설정
    chart_font_style = dict(
        family="Arial, sans-serif",
        size=18,  # 기본 글자 크기 대폭 확대
        color="black"
    )

    with tab1:
        st.write(f"### 최근 30일 일별 시세 ({currency})")
        selected_daily = st.multiselect("분석 품목 선택", items, default=['Cu(구리)'], key="daily")
        if selected_daily:
            daily_df = df.head(30).sort_values('날짜')
            y_cols = [f"{s}{currency_col_suffix}" for s in selected_daily]
            fig_daily = px.line(daily_df, x='날짜', y=y_cols, markers=True, title=f"일별 {currency} 시세 추이")

            # 그래프 글자 크기 조절
            fig_daily.update_layout(
                font=chart_font_style,
                title_font_size=26,
                legend_font_size=18,
                xaxis_title_font_size=20,
                yaxis_title_font_size=20,
                hovermode="x unified"
            )
            st.plotly_chart(fig_daily, use_container_width=True)

    with tab2:
        st.write(f"### 월별 평균 시세 추이 ({currency})")
        selected_monthly = st.multiselect("분석 품목 선택", items, default=['Cu(구리)'], key="monthly")

        if selected_monthly:
            df_m = df.copy()
            df_m['연월'] = df_m['날짜'].dt.to_period('M').astype(str)
            val_cols = [f"{s}{currency_col_suffix}" for s in selected_monthly]
            monthly_avg = df_m.groupby('연월')[val_cols].mean().reset_index().sort_values('연월')

            fig_monthly = px.line(monthly_avg, x='연월', y=val_cols, markers=True, title=f"월간 평균 {currency} 변동")

            # 그래프 글자 크기 조절
            fig_monthly.update_layout(
                font=chart_font_style,
                title_font_size=26,
                legend_font_size=18,
                xaxis_title_font_size=20,
                yaxis_title_font_size=20,
                hovermode="x unified",
                yaxis_tickformat=',.0f' if currency == "원화 (KRW)" else ',.1f'
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

    with st.expander("📝 전체 원천 데이터 확인"):
        display_df = df.copy()
        display_df['날짜'] = display_df['날짜'].dt.strftime('%Y-%m-%d')
        st.dataframe(display_df, use_container_width=True)

else:
    st.error("데이터 로딩 실패")