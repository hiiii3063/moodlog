
import os
import base64
import calendar
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from werkzeug.security import generate_password_hash, check_password_hash


# ==================================================
# 1. 기본 설정
# ==================================================

st.set_page_config(
    page_title="감정날씨 연구소",
    page_icon="🌦️",
    layout="wide"
)

DB_PATH = os.environ.get("DB_PATH", "emotion_weather.db")
MAX_PHOTO_SIZE = 5 * 1024 * 1024
DIARY_PHOTO_WIDTH = 300
CALENDAR_PHOTO_WIDTH = 200

WEATHER_OPTIONS = {
    "맑음": {"score": 5, "emoji": "☀️"},
    "무지개": {"score": 5, "emoji": "🌈"},
    "구름 조금": {"score": 4, "emoji": "🌤️"},
    "흐림": {"score": 3, "emoji": "☁️"},
    "비": {"score": 2, "emoji": "🌧️"},
    "번개": {"score": 1, "emoji": "⛈️"},
    "안개": {"score": 3, "emoji": "🌫️"},
}

EMOTION_ADVICE = {
    "맑음": "기분이 좋았던 이유를 기록해 보세요. 즐거웠던 순간을 기억하는 데 도움이 됩니다.",
    "무지개": "여러 감정이 함께 느껴졌을 수 있어요. 기뻤던 점과 아쉬웠던 점을 나누어 적어 보세요.",
    "구름 조금": "마음이 복잡하다면 잠깐 쉬면서 지금 느끼는 감정을 살펴보세요.",
    "흐림": "기분이 가라앉을 때는 좋아하는 음악을 듣거나 편안한 활동을 해 보세요.",
    "비": "속상한 감정도 자연스러운 감정이에요. 믿을 수 있는 사람에게 마음을 이야기해 보세요.",
    "번개": "감정이 강하게 느껴질 때는 잠시 멈추고 천천히 호흡해 보세요.",
    "안개": "감정이 무엇인지 정확히 알기 어렵다면 가까운 감정 단어부터 찾아보세요.",
}


# ==================================================
# 2. 디자인
# ==================================================

st.markdown("""
<style>
/* 전체 배경: 부드러운 연노랑 */
.stApp {
    background-color: #FFF9E8;
    color: #4F5847;
}

/* 제목 */
h1, h2, h3 {
    color: #536448;
    letter-spacing: -0.5px;
}

/* 본문 */
p, label, .stMarkdown {
    color: #5D6255;
}

/* 사이드바 */
section[data-testid="stSidebar"] {
    background-color: #F2F5E8;
    border-right: 1px solid #E1E8D3;
}

/* 입력 칸 */
.stTextInput input,
.stTextArea textarea,
.stDateInput input,
.stNumberInput input {
    background-color: #FFFEF8;
    border: 1px solid #DCE5CD;
    border-radius: 12px;
    color: #4F5847;
}

/* 선택 메뉴 */
.stSelectbox [data-baseweb="select"] > div {
    background-color: #FFFEF8;
    border-color: #DCE5CD;
    border-radius: 12px;
}

/* 버튼 */
