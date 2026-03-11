import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime

# --- 기본 설정 ---
st.set_page_config(page_title="LME 글로벌 모니터링 & 월별 분석", layout="wide")


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
            # 월별 통계를 위해 충분한 기간(6개월) 데이터를 가져옵니다.
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if not data.empty:
                temp_df = data[['Close']].reset_index()
                temp_df.columns = ['날짜', name]
                combined_data.append(temp_df.set_index('날짜'))
        except:
            continue

    if not combined_data: return None

    # 데이터 병합 및 결측치 처리
    df = pd.concat(combined_data, axis=1).sort_index(ascending=False).reset_index()
    df = df.fillna(method='ffill').fillna(method='bfill')  # 앞뒤 값으로 빈칸 채우기

    # 단위 환산 및 원화 계산
    for name in tickers.keys():
        if name in df.columns:
            if name == "Cu(구리)":
                df[name] = df[name] * 2204.62
            df[f"{name}_KRW"] = df[name] * rate

    return df


# --- UI 레이아웃 ---
st.title("📊 LME 비철금속 원화(KRW) 모니터링 시스템")

exchange_rate = fetch_exchange_rate()
df = fetch_global_lme(exchange_rate)

if df is not None and not df.empty:
    # 사이드바 정보
    st.sidebar.success(f"**현재 환율:** {exchange_rate:,.2f} 원/달러")
    st.sidebar.info("💡 야후 파이낸스 글로벌 데이터를 기준으로 실시간 환산됩니다.")

    # 1. 상단 요약 (최신 영업일 기준)
    latest = df.iloc[0]
    st.subheader(f"📅 데이터 기준일: {latest['날짜'].strftime('%Y-%m-%d')}")

    m1, m2, m3 = st.columns(3)
    items = ['Cu(구리)', 'Al(알루미늄)', 'Zn(아연)']
    for i, item in enumerate(items):
        if f"{item}_KRW" in df.columns:
            curr = latest[f"{item}_KRW"]
            prev = df.iloc[1][f"{item}_KRW"] if len(df) > 1 else curr
            [m1, m2, m3][i].metric(label=f"{item} (KRW/ton)",
                                   value=f"{int(curr):,}원",
                                   delta=f"{int(curr - prev):,}원")

    st.divider()

    # 2. 메인 분석 탭
    tab1, tab2 = st.tabs(["📈 일별 시세 추이", "📊 월별 평균 분석"])

    with tab1:
        st.write("### 최근 30일 가격 변동")
        selected_daily = st.multiselect("분석 품목 선택", items, default=['Cu(구리)'], key="daily")
        if selected_daily:
            # 최근 30개 데이터만 시각화
            daily_df = df.head(30).sort_values('날짜')
            y_cols = [f"{s}_KRW" for s in selected_daily]
            fig_daily = px.line(daily_df, x='날짜', y=y_cols, markers=True,
                                title="일별 원화 시세 (최근 30일)")
            st.plotly_chart(fig_daily, use_container_width=True)

    with tab2:
        st.write("### 월별 평균 가격 (Monthly Avg.)")
        selected_monthly = st.multiselect("분석 품목 선택", items, default=['Cu(구리)'], key="monthly")

        if selected_monthly:
            # 월별 데이터 그룹화
            df_m = df.copy()
            df_m['연월'] = df_m['날짜'].dt.to_period('M').astype(str)

            # 수치 데이터만 평균 계산
            val_cols = [f"{s}_KRW" for s in selected_monthly]
            monthly_avg = df_m.groupby('연월')[val_cols].mean().reset_index()
            monthly_avg = monthly_avg.sort_values('연월')

            # 막대 그래프로 시각화
            fig_monthly = px.bar(monthly_avg, x='연월', y=val_cols, barmode='group',
                                 title="월 단위 평균 단가 비교",
                                 text_auto=',.0f')
            fig_monthly.update_traces(textposition='outside')
            st.plotly_chart(fig_monthly, use_container_width=True)

    # 3. 데이터 상세 보기
    with st.expander("📝 전체 원천 데이터 확인"):
        st.dataframe(df, use_container_width=True)

else:
    st.error("데이터 로딩에 실패했습니다. 연결 상태를 확인해주세요.")