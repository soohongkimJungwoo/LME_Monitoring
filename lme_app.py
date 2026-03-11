import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime

# --- 설정 ---
st.set_page_config(page_title="LME 글로벌 모니터링", layout="wide")


# --- 1. 환율 가져오기 (야후 파이낸스 - 클라우드용) ---
@st.cache_data(ttl=3600)
def fetch_exchange_rate():
    try:
        krw = yf.Ticker("KRW=X")
        # 최근 3일치 데이터를 가져와서 가장 마지막 유효한 값을 선택
        hist = krw.history(period="3d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        return 1450.0
    except:
        return 1450.0


# --- 2. LME 시세 가져오기 (결측치 처리 강화) ---
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
            data = yf.download(ticker, period="1mo", interval="1d", progress=False)
            if not data.empty:
                temp_df = data[['Close']].reset_index()
                # 멀티인덱스 방지 및 컬럼명 정리
                temp_df.columns = ['날짜', name]
                temp_df['날짜'] = temp_df['날짜'].dt.strftime('%Y-%m-%d')
                combined_data.append(temp_df.set_index('날짜'))
        except:
            continue

    if not combined_data: return None

    # 데이터 합산 및 결측치 처리
    df = pd.concat(combined_data, axis=1).sort_index(ascending=False).reset_index()
    # 결측치를 0으로 채움 (ValueError 방지 핵심)
    df = df.fillna(0)

    for name in tickers.keys():
        if name in df.columns:
            if name == "Cu(구리)":
                df[name] = df[name] * 2204.62
            df[f"{name}_KRW"] = df[name] * rate

    return df


# --- UI 구현 ---
st.title("🌐 LME 글로벌 시세 모니터링")

exchange_rate = fetch_exchange_rate()
df = fetch_global_lme(exchange_rate)

if df is not None and not df.empty:
    st.sidebar.success(f"**적용 환율:** {exchange_rate:,.2f} 원")

    # 최신 데이터 추출
    latest = df.iloc[0]
    st.subheader(f"📅 데이터 기준일: {latest['날짜']}")

    m1, m2, m3 = st.columns(3)
    items = ['Cu(구리)', 'Al(알루미늄)', 'Zn(아연)']

    for i, item in enumerate(items):
        if f"{item}_KRW" in df.columns:
            curr_val = latest[f"{item}_KRW"]
            # 이전 영업일 데이터가 없을 경우를 대비해 0으로 처리
            prev_val = df.iloc[1][f"{item}_KRW"] if len(df) > 1 else curr_val

            # 델타 값 계산
            delta_val = curr_val - prev_val

            # 에러 방지용 포맷팅: f-string 내에서 직접 반올림 및 콤마 처리
            [m1, m2, m3][i].metric(
                label=f"{item} (KRW/ton)",
                value=f"{int(curr_val):,}원" if curr_val > 0 else "데이터 없음",
                delta=f"{int(delta_val):,}원" if curr_val > 0 else None
            )

    st.divider()

    # 그래프 및 상세 표
    tab1, tab2 = st.tabs(["📉 시세 추이", "📝 데이터 상세"])
    with tab1:
        selected = st.multiselect("품목 선택", items, default=['Cu(구리)', 'Al(알루미늄)'])
        if selected:
            y_cols = [f"{s}_KRW" for s in selected]
            fig = px.line(df.sort_values('날짜'), x='날짜', y=y_cols, markers=True)
            st.plotly_chart(fig, use_container_width=True)
    with tab2:
        st.dataframe(df, use_container_width=True)
else:
    st.error("데이터를 불러오는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")