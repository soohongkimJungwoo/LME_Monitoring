import streamlit as st
import pandas as pd
import yfinance as yf
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import re
from datetime import datetime, timedelta

# --- 설정 ---
EXCHANGE_URL = "http://www.smbs.biz/ExRate/TodayExRate.jsp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}

st.set_page_config(page_title="LME 글로벌 모니터링", layout="wide")


# --- 1. 환율 가져오기 (기존과 동일하되 백업 로직 강화) ---
@st.cache_data(ttl=3600)
def fetch_exchange_rate():
    try:
        response = requests.get(EXCHANGE_URL, headers=HEADERS, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        target_div = soup.select_one('div.table_type, div[class^="table_type"]')
        rows = target_div.find_all('tr') if target_div else soup.find_all('tr')
        for row in rows:
            if 'USD' in row.get_text():
                match = re.search(r'(\d+,\d+\.\d+|\d+\.\d+)', row.get_text())
                if match:
                    return float(match.group(1).replace(',', ''))
        return 1450.0  # 실패 시 최근 평균 환율
    except:
        return 1450.0


# --- 2. 야후 파이낸스에서 LME 시세 가져오기 ---
@st.cache_data(ttl=3600)
def fetch_global_lme(rate):
    # 야후 파이낸스 LME/금속 티커 (선물 기준)
    # 구리(HG=F), 알루미늄(ALI=F), 아연(ZNC=F), 니켈(NICKEL), 주석(TIN) 등
    tickers = {
        "Cu(구리)": "HG=F",  # COMEX Copper (LME와 매우 유사하게 연동)
        "Al(알루미늄)": "ALI=F",
        "Zn(아연)": "ZNC=F",
        "Pb(납)": "LEAD=F",
        "Ni(니켈)": "NI=F",
        "Sn(주석)": "TIN=F"
    }

    combined_data = []

    for name, ticker in tickers.items():
        try:
            # 최근 30일 데이터 추출
            data = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if not data.empty:
                temp_df = data[['Close']].reset_index()
                temp_df.columns = ['날짜', name]
                temp_df['날짜'] = temp_df['날짜'].dt.strftime('%Y-%m-%d')
                combined_data.append(temp_df.set_index('날짜'))
        except:
            continue

    if not combined_data: return None

    # 데이터 합치기
    df = pd.concat(combined_data, axis=1).sort_index(ascending=False).reset_index()

    # 원화 환산 컬럼 추가
    for name in tickers.keys():
        if name in df.columns:
            # 야후 파이낸스의 구리(HG=F)는 파운드(lb) 단위일 수 있어 톤(ton)으로 환산 필요 (1톤 = 2204.62파운드)
            if name == "Cu(구리)":
                df[name] = df[name] * 2204.62

            df[f"{name}_KRW"] = df[name] * rate

    return df


# --- UI 구현 ---
st.title("🌐 LME 글로벌 시세 모니터링 (배포 버전)")

exchange_rate = fetch_exchange_rate()
df = fetch_global_lme(exchange_rate)

# 사이드바
st.sidebar.header("⚙️ 설정 및 지표")
st.sidebar.success(f"**현재 환율 (USD/KRW)**\n\n### {exchange_rate:,.2f} 원")
input_rate = st.sidebar.number_input("환율 수동 조정 (필요시)", value=exchange_rate)

if df is not None:
    # 최신가 요약
    latest_prices = df.iloc[0]
    st.subheader(f"📅 최근 업데이트: {latest_prices['날짜']}")

    m1, m2, m3 = st.columns(3)
    items = ['Cu(구리)', 'Al(알루미늄)', 'Zn(아연)']
    for i, item in enumerate(items):
        if item in df.columns:
            curr_val = latest_prices[f"{item}_KRW"]
            prev_val = df.iloc[1][f"{item}_KRW"] if len(df) > 1 else curr_val
            [m1, m2, m3][i].metric(label=f"{item} (KRW/ton)",
                                   value=f"{int(curr_val):,}원",
                                   delta=f"{int(curr_val - prev_val):,}원")

    st.divider()

    # 그래프 및 테이블
    tab1, tab2 = st.tabs(["📉 시세 그래프", "📝 데이터 테이블"])

    with tab1:
        mode = st.radio("통화", ["KRW", "USD"], horizontal=True)
        all_items = [c for c in df.columns if "_KRW" not in c and c != "날짜"]
        selected = st.multiselect("품목 선택", all_items, default=all_items[:2])

        if selected:
            chart_df = df.sort_values('날짜')
            y_cols = [f"{s}_KRW" if mode == "KRW" else s for s in selected]
            fig = px.line(chart_df, x='날짜', y=y_cols, markers=True, title="글로벌 금속 시세 추이")
            st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.dataframe(df, use_container_width=True)
else:
    st.error("데이터를 가져올 수 없습니다. 야후 파이낸스 연결을 확인하세요.")