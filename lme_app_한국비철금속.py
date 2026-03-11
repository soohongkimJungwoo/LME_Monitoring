import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import re

# --- 기본 설정 ---
LME_URL = "https://www.nonferrous.or.kr/stats/?act=sub3"
EXCHANGE_URL = "http://www.smbs.biz/ExRate/TodayExRate.jsp"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

st.set_page_config(page_title="LME 원화 환산 모니터링", layout="wide")


# --- 1. 환율 가져오기 함수 (Regex 수정 완료) ---
@st.cache_data(ttl=3600)
def fetch_exchange_rate():
    try:
        response = requests.get(EXCHANGE_URL, headers=HEADERS, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')

        target_div = soup.select_one('div.table_type, div[class^="table_type"]')
        rows = target_div.find_all('tr') if target_div else soup.find_all('tr')

        for row in rows:
            row_text = row.get_text(strip=True)
            if 'USD' in row_text or '미국 달러' in row_text:
                cells = row.find_all(['td', 'th'])
                for cell in cells:
                    val_str = cell.get_text(strip=True).replace(',', '')
                    # 자릿수 제한 없는 정규표현식으로 1,000원대 환율 대응
                    match = re.search(r'(\d+\.\d+)', val_str)
                    if match:
                        rate = float(match.group(1))
                        if rate > 1000:
                            return rate

        return 1472.80  # 수집 실패 시 기본 예비값
    except Exception as e:
        st.error(f"환율 수집 오류: {e}")
        return 1472.80


# --- 2. LME 데이터 수집 함수 ---
@st.cache_data(ttl=3600)
def fetch_lme_with_krw(rate):
    try:
        # timeout을 10에서 30으로 늘리고, headers를 보강합니다.
        response = requests.get(LME_URL, headers=HEADERS, timeout=30)
        response.raise_for_status()  # 접속 실패 시 즉시 에러 발생

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')

        if not table:
            return None

        df = pd.read_html(str(table), flavor='lxml')[0]
        # ... (이후 컬럼 정리 로직은 동일)
        return df
    except requests.exceptions.Timeout:
        st.error("⚠️ 서버 응답 시간이 초과되었습니다. (해외망 지연)")
        return None
    except Exception as e:
        st.error(f"⚠️ 데이터 수집 중 오류 발생: {e}")
        return None


# --- UI 레이아웃 ---
st.title("📊 LME 비철금속 원화(KRW) 모니터링")

# 데이터 로드
exchange_rate = fetch_exchange_rate()  # 수집된 환율 정보
df = fetch_lme_with_krw(exchange_rate)

if df is not None:
    # --- 사이드바: 요청하신 부분 (success 메시지에 변수 반영) ---
    st.sidebar.header("💱 시장 지표")

    # fetch_exchange_rate로 가져온 rate 정보를 보여줍니다.
    st.sidebar.success(f"""
    **현재 환율 (USD/KRW)**  {exchange_rate:,.2f} 원
    *(기준: 서울외국환중개 매매기준율)*
    """)

    st.sidebar.info("💡 1시간 간격으로 자동 업데이트됩니다.")
    # --------------------------------------------------

    # 메인 화면: 최신 시세 요약
    latest_date = df.iloc[0]['날짜']
    st.subheader(f"📅 업데이트: {latest_date}")

    m1, m2, m3 = st.columns(3)
    items_to_show = ['Cu(구리)', 'Al(알루미늄)', 'Zn(아연)']
    for i, item in enumerate(items_to_show):
        curr_krw = df.iloc[0][f"{item}_KRW"]
        prev_krw = df.iloc[1][f"{item}_KRW"] if len(df) > 1 else curr_krw
        delta_val = curr_krw - prev_krw

        [m1, m2, m3][i].metric(
            label=f"{item} (KRW/ton)",
            value=f"{int(curr_krw):,}원",
            delta=f"{int(delta_val):,}원"
        )

    st.divider()

    # 옵션 및 그래프
    col_chart, col_opt = st.columns([3, 1])
    with col_opt:
        display_mode = st.radio("통화 선택", ["원화(KRW)", "달러(USD)"])
        all_items = ['Cu(구리)', 'Al(알루미늄)', 'Zn(아연)', 'Pb(납)', 'Ni(니켈)', 'Sn(주석)']
        selected = st.multiselect("품목 선택", all_items, default=['Cu(구리)', 'Al(알루미늄)'])

    with col_chart:
        if selected:
            chart_df = df.sort_values('날짜')
            y_cols = [f"{m}_KRW" if display_mode == "원화(KRW)" else m for m in selected]
            fig = px.line(chart_df, x='날짜', y=y_cols, markers=True,
                          title=f"LME {display_mode} 시세 변동 추이")
            st.plotly_chart(fig, use_container_width=True)

    with st.expander("📝 전체 데이터 표 확인"):
        st.dataframe(df, use_container_width=True)

else:
    st.error("데이터를 불러올 수 없습니다.")