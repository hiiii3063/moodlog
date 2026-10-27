
# ==========================================
# 감정날씨 연구소
# 감정 기록 + 일반 일기 + 사진 첨부
# 파일명: main.py
# ==========================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import calendar
import os

from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash


# ------------------------------------------
# 1. 기본 설정
# ------------------------------------------

st.set_page_config(
    page_title="감정날씨 연구소",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 데이터베이스 파일
# 주의: Streamlit Cloud의 로컬 파일은 영구 저장이 보장되지 않음
DB_PATH = os.environ.get("DB_PATH", "emotion_weather.db")

# 사진 한 장의 최대 업로드 크기: 5MB
MAX_PHOTO_SIZE = 5 * 1024 * 1024


# ------------------------------------------
# 2. 화면 디자인
# ------------------------------------------

st.markdown("""
<style>
    .stApp {
        background-color: #FFF9F0;
        color: #51483F;
    }

    h1, h2, h3 {
        color: #805B46;
    }

    [data-testid="stSidebar"] {
        background-color: #FFF0D9;
    }

    div.stButton > button {
        background-color: #F6D6A8;
        color: #594735;
        border: 1px solid #EBC38C;
        border-radius: 12px;
        min-height: 42px;
    }

    div.stButton > button:hover {
        background-color: #F0C68C;
        color: #4D3827;
    }

    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F1DFC8;
        padding: 16px;
        border-radius: 15px;
    }

    .weather-banner {
        background-color: #FFF0D9;
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 18px;
    }

    .calendar-cell {
        background-color: #FFFFFF;
        border: 1px solid #F0E2D2;
        border-radius: 10px;
        padding: 7px 2px;
        min-height: 72px;
        text-align: center;
        margin-bottom: 5px;
    }

    .calendar-empty {
        background-color: #F9F0E6;
        border-radius: 10px;
        min-height: 72px;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------
# 3. 감정 종류와 추천 활동
# ------------------------------------------

EMOTIONS = {
    "맑음": {
        "emoji": "☀️",
        "score": 5,
        "description": "기분이 좋고 마음이 가벼워요."
    },
    "무지개": {
        "emoji": "🌈",
        "score": 5,
        "description": "기대하거나 뿌듯한 마음이 들어요."
    },
    "구름 조금": {
        "emoji": "⛅",
        "score": 4,
        "description": "편안하지만 조금 신경 쓰이는 일이 있어요."
    },
    "흐림": {
        "emoji": "☁️",
        "score": 3,
        "description": "기분이 가라앉거나 마음이 복잡해요."
    },
    "비": {
        "emoji": "🌧️",
        "score": 2,
        "description": "슬프거나 속상한 마음이 들어요."
    },
    "번개": {
        "emoji": "⛈️",
        "score": 1,
        "description": "화가 나거나 긴장되는 마음이 커요."
    },
    "안개": {
        "emoji": "🌫️",
        "score": 3,
        "description": "내 감정이 무엇인지 잘 모르겠어요."
    }
}

ADVICE = {
    "맑음": [
        "오늘 기분이 좋았던 이유를 한 가지 적어 보기",
        "좋은 기분을 친구나 가족과 나누기",
        "오늘의 즐거운 순간을 사진이나 그림으로 남기기"
    ],
    "무지개": [
        "오늘 해낸 일을 작은 성취 노트에 적기",
        "내가 좋아하는 활동을 충분히 즐기기",
        "나를 응원해 준 사람에게 고마움 표현하기"
    ],
    "구름 조금": [
        "잠깐 자리에서 일어나 몸을 움직이기",
        "걱정되는 일을 종이에 적고 하나씩 살펴보기",
        "좋아하는 음악을 들으며 잠깐 쉬기"
    ],
    "흐림": [
        "지금 마음에 떠오르는 생각을 세 문장으로 적기",
        "물 한 잔을 마시고 조용한 곳에서 쉬기",
        "믿을 만한 사람에게 오늘 기분을 이야기하기"
    ],
    "비": [
        "속상한 이유를 판단하지 않고 글로 적어 보기",
        "편안한 음악을 듣거나 좋아하는 그림 그리기",
        "믿을 만한 어른이나 친구에게 마음을 나누기"
    ],
    "번개": [
        "잠깐 멈추고 천천히 호흡하기",
        "감정이 가라앉을 때까지 안전한 곳에서 쉬기",
        "무엇이 불편했는지 차분해진 뒤 문장으로 적기"
    ],
    "안개": [
        "몸에서 느껴지는 감각을 천천히 살펴보기",
        "기쁨, 슬픔, 걱정 중 가까운 감정이 있는지 찾아보기",
        "지금 필요한 것이 휴식인지 대화인지 생각해 보기"
    ]
}


# ------------------------------------------
# 4. 데이터베이스 만들기
# ------------------------------------------

def get_connection():
    """데이터베이스에 연결"""
    return sqlite3.connect(DB_PATH)


def init_database():
    """계정, 감정 기록, 일반 일기 표를 만듦"""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 사용자 계정
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # 감정 날씨 기록
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emotion_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                record_date TEXT NOT NULL,
                emotion TEXT NOT NULL,
                reason TEXT,
                stress INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, record_date)
            )
        """)

        # 일반 일기
        # 사진은 파일 경로가 아닌 데이터 자체를 저장함
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                diary_date TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                photo_data BLOB,
                photo_mime TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(user_id, diary_date)
            )
        """)

        conn.commit()


init_database()


# ------------------------------------------
# 5. 회원가입과 로그인
# ------------------------------------------

def create_account(username, password):
    """새 계정을 만들고 비밀번호를 해시로 저장"""
    username = username.strip()

    if len(username) < 3 or len(username) > 20:
        return False, "아이디는 3~20자로 입력해 주세요."

    if not username.replace("_", "").isalnum():
        return False, "아이디는 영문, 숫자, 밑줄(_)만 사용할 수 있어요."

    if len(password) < 8:
        return False, "비밀번호는 8자 이상으로 설정해 주세요."

    password_hash = generate_password_hash(password)

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO users
                (username, password_hash, created_at)
                VALUES (?, ?, ?)
            """, (
                username,
                password_hash,
                datetime.now().isoformat(timespec="seconds")
            ))
            conn.commit()

        return True, "계정이 만들어졌어요. 로그인해 주세요."

    except sqlite3.IntegrityError:
        return False, "이미 사용 중인 아이디예요."


def login_account(username, password):
    """아이디와 비밀번호 확인"""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT id, password_hash
            FROM users
            WHERE username = ?
        """, (username.strip(),)).fetchone()

    if row and check_password_hash(row[1], password):
        return row[0]

    return None


# 로그인 상태 유지
if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = None


# ------------------------------------------
# 6. 감정 기록 저장 및 불러오기
# ------------------------------------------

def save_record(user_id, record_date, emotion, reason, stress):
    """같은 날짜에 기록이 있으면 수정하고 없으면 새로 저장"""
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO emotion_records
            (user_id, record_date, emotion, reason, stress)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, record_date)
            DO UPDATE SET
                emotion = excluded.emotion,
                reason = excluded.reason,
                stress = excluded.stress
        """, (
            user_id,
            record_date.isoformat(),
            emotion,
            reason.strip(),
            stress
        ))
        conn.commit()


def load_records(user_id):
    """로그인한 사용자의 감정 기록만 불러오기"""
    with get_connection() as conn:
        df = pd.read_sql_query("""
            SELECT record_date, emotion, reason, stress
            FROM emotion_records
            WHERE user_id = ?
            ORDER BY record_date
        """, conn, params=(user_id,))

    if not df.empty:
        df["record_date"] = pd.to_datetime(df["record_date"])
        df["stress"] = df["stress"].astype(int)
        df["emotion_score"] = df["emotion"].map(
            lambda x: EMOTIONS.get(x, {}).get("score", 3)
        )

    return df


def delete_record(user_id, record_date):
    """감정 기록 삭제"""
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM emotion_records
            WHERE user_id = ? AND record_date = ?
        """, (user_id, record_date.isoformat()))
        conn.commit()


# ------------------------------------------
# 7. 일반 일기: 저장, 불러오기, 삭제
# ------------------------------------------

def load_diary(user_id, diary_date):
    """선택한 날짜의 일기를 불러오기"""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT title, content, photo_data, photo_mime, updated_at
            FROM diaries
            WHERE user_id = ? AND diary_date = ?
        """, (user_id, diary_date.isoformat())).fetchone()

    return row


def load_diary_list(user_id):
    """일기 목록을 날짜순으로 불러오기"""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT diary_date, title, updated_at,
                   CASE WHEN photo_data IS NULL THEN 0 ELSE 1 END
            FROM diaries
            WHERE user_id = ?
            ORDER BY diary_date DESC
        """, (user_id,)).fetchall()

    return rows


def save_diary(user_id, diary_date, title, content, uploaded_photo):
    """
    일기를 저장함.
    새 사진을 올리지 않았다면 기존 사진을 유지함.
    """
    photo_data = None
    photo_mime = None

    if uploaded_photo is not None:
        photo_data = uploaded_photo.getvalue()
        photo_mime = uploaded_photo.type

        if len(photo_data) > MAX_PHOTO_SIZE:
            return False, "사진은 한 장당 5MB 이하로 올려 주세요."

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO diaries
            (user_id, diary_date, title, content,
             photo_data, photo_mime, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, diary_date)
            DO UPDATE SET
                title = excluded.title,
                content = excluded.content,
                photo_data = COALESCE(
                    excluded.photo_data, diaries.photo_data
                ),
                photo_mime = COALESCE(
                    excluded.photo_mime, diaries.photo_mime
                ),
                updated_at = excluded.updated_at
        """, (
            user_id,
            diary_date.isoformat(),
            title.strip(),
            content,
            photo_data,
            photo_mime,
            datetime.now().isoformat(timespec="seconds")
        ))
        conn.commit()

    return True, "일기를 저장했어요."


def delete_diary(user_id, diary_date):
    """선택한 날짜의 일기 전체를 삭제"""
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM diaries
            WHERE user_id = ? AND diary_date = ?
        """, (user_id, diary_date.isoformat()))
        conn.commit()


def delete_diary_photo(user_id, diary_date):
    """일기는 유지하고 사진만 삭제"""
    with get_connection() as conn:
        conn.execute("""
            UPDATE diaries
            SET photo_data = NULL,
                photo_mime = NULL,
                updated_at = ?
            WHERE user_id = ? AND diary_date = ?
        """, (
            datetime.now().isoformat(timespec="seconds"),
            user_id,
            diary_date.isoformat()
        ))
        conn.commit()


# ------------------------------------------
# 8. 로그인 화면
# ------------------------------------------

def show_login_page():
    st.markdown(
        "<div class='weather-banner'>"
        "<h1>🌦️ 감정날씨 연구소</h1>"
        "<p>오늘 내 마음에는 어떤 날씨가 찾아왔나요?</p>"
        "<p>감정도 기록하고, 하루의 이야기도 일기로 남겨 봐요.</p>"
        "</div>",
        unsafe_allow_html=True
    )

    login_tab, signup_tab = st.tabs(["로그인", "회원가입"])

    with login_tab:
        st.subheader("다시 만나서 반가워요!")

        with st.form("login_form"):
            username = st.text_input("아이디")
            password = st.text_input("비밀번호", type="password")
            submitted = st.form_submit_button(
                "로그인",
                use_container_width=True
            )

        if submitted:
            user_id = login_account(username, password)

            if user_id is not None:
                st.session_state.user_id = user_id
                st.session_state.username = username.strip()
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호를 확인해 주세요.")

    with signup_tab:
        st.subheader("새로운 감정 연구원 되기")

        with st.form("signup_form"):
            new_username = st.text_input(
                "새 아이디",
                help="영문, 숫자, 밑줄을 사용한 3~20자"
            )
            new_password = st.text_input(
                "새 비밀번호",
                type="password",
                help="8자 이상으로 설정해 주세요."
            )
            confirm_password = st.text_input(
                "비밀번호 다시 입력",
                type="password"
            )
            signup_submitted = st.form_submit_button(
                "계정 만들기",
                use_container_width=True
            )

        if signup_submitted:
            if new_password != confirm_password:
                st.error("두 비밀번호가 서로 달라요.")
            else:
                success, message = create_account(
                    new_username,
                    new_password
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.caption(
        "감정에는 정답이 없어요. "
        "이곳은 내 마음과 하루를 천천히 살펴보는 공간이에요."
    )


# ------------------------------------------
# 9. 오늘의 감정 날씨
# ------------------------------------------

def show_today_page(df):
    st.header("☀️ 오늘의 감정 날씨")
    st.write("오늘 내 마음을 날씨로 표현해 볼까요?")

    col1, col2 = st.columns(2)

    with col1:
        record_date = st.date_input(
            "기록할 날짜",
            value=date.today(),
            key="emotion_record_date"
        )

        selected_emotion = st.selectbox(
            "오늘의 마음 날씨",
            list(EMOTIONS.keys()),
            format_func=lambda x: f"{EMOTIONS[x]['emoji']} {x}"
        )

        st.info(EMOTIONS[selected_emotion]["description"])

        reason = st.text_area(
            "이런 날씨가 찾아온 이유는 무엇인가요?",
            placeholder="예: 친구와 즐겁게 이야기해서 기분이 좋았다.",
            max_chars=500,
            height=120
        )

        stress = st.slider(
            "오늘 스트레스는 어느 정도인가요?",
            min_value=0,
            max_value=10,
            value=3,
            help="0은 스트레스가 거의 없음, 10은 매우 높음을 뜻해요."
        )

        if st.button("💾 감정 기록 저장하기", use_container_width=True):
            save_record(
                st.session_state.user_id,
                record_date,
                selected_emotion,
                reason,
                stress
            )
            st.success("오늘의 마음 날씨를 저장했어요!")
            st.rerun()

    with col2:
        st.markdown(
            "<div class='weather-banner'>"
            "<h2>나의 마음 날씨</h2>"
            f"<div style='font-size:75px;text-align:center;'>"
            f"{EMOTIONS[selected_emotion]['emoji']}</div>"
            f"<h3 style='text-align:center;'>{selected_emotion}</h3>"
            f"<p style='text-align:center;'>"
            f"{EMOTIONS[selected_emotion]['description']}</p>"
            "</div>",
            unsafe_allow_html=True
        )

        st.markdown("### 오늘의 작은 질문")
        st.write("- 오늘 나를 가장 기쁘게 하거나 힘들게 한 일은?")
        st.write("- 지금 나에게 필요한 것은 무엇일까?")
        st.write("- 내일의 나에게 어떤 말을 해 주고 싶을까?")

        if not df.empty:
            previous = df[
                df["record_date"].dt.date == record_date
            ]

            if not previous.empty:
                old = previous.iloc[0]
                st.caption(
                    f"이 날짜에는 이미 {old['emotion']} 기록이 있어요. "
                    "저장하면 기존 감정 기록이 수정돼요."
                )


# ------------------------------------------
# 10. 감정 달력
# ------------------------------------------

def show_calendar_page(df):
    st.header("🗓️ 감정 달력")
    st.write("날짜별로 내 마음의 날씨를 살펴봐요.")

    today = date.today()

    col1, col2 = st.columns(2)

    with col1:
        year = st.selectbox(
            "연도",
            list(range(today.year - 5, today.year + 1)),
            index=5,
            key="calendar_year"
        )

    with col2:
        month = st.selectbox(
            "월",
            list(range(1, 13)),
            index=today.month - 1,
            key="calendar_month"
        )

    # 감정 기록을 날짜별로 연결
    record_map = {}

    if not df.empty:
        for _, row in df.iterrows():
            d = row["record_date"].date()

            if d.year == year and d.month == month:
                record_map[d.day] = row["emotion"]

    # 일반 일기가 있는 날짜 확인
    diary_dates = {
        datetime.strptime(row[0], "%Y-%m-%d").date().day
        for row in load_diary_list(st.session_state.user_id)
        if datetime.strptime(row[0], "%Y-%m-%d").date().year == year
        and datetime.strptime(row[0], "%Y-%m-%d").date().month == month
    }

    weekday_cols = st.columns(7)

    for col, weekday in zip(
        weekday_cols,
        ["월", "화", "수", "목", "금", "토", "일"]
    ):
        col.markdown(f"**{weekday}**")

    for week in calendar.monthcalendar(year, month):
        cols = st.columns(7)

        for col, day_number in zip(cols, week):
            with col:
                if day_number == 0:
                    st.markdown(
                        "<div class='calendar-empty'></div>",
                        unsafe_allow_html=True
                    )
                else:
                    emotion = record_map.get(day_number)

                    if emotion:
                        emoji = EMOTIONS[emotion]["emoji"]
                        emotion_text = emotion
                    else:
                        emoji = "📔" if day_number in diary_dates else "·"
                        emotion_text = (
                            "일기 있음" if day_number in diary_dates
                            else "기록 없음"
                        )

                    st.markdown(
                        "<div class='calendar-cell'>"
                        f"<div>{day_number}일</div>"
                        f"<div style='font-size:22px;'>{emoji}</div>"
                        f"<div style='font-size:11px;'>{emotion_text}</div>"
                        "</div>",
                        unsafe_allow_html=True
                    )

    st.caption("날씨 아이콘은 감정 기록, 📔는 일반 일기가 있는 날이에요.")

    selected_day = st.date_input(
        "자세히 살펴볼 날짜",
        value=today,
        key="calendar_selected_date"
    )

    selected_records = df[
        df["record_date"].dt.date == selected_day
    ] if not df.empty else pd.DataFrame()

    if not selected_records.empty:
        row = selected_records.iloc[0]
        st.markdown(
            f"### {EMOTIONS[row['emotion']]['emoji']} "
            f"{selected_day}의 감정 기록"
        )
        st.write(f"감정: {row['emotion']}")
        st.write(f"이유: {row['reason'] or '작성한 이유가 없어요.'}")
        st.write(f"스트레스: {row['stress']} / 10")

        if st.button("이 날짜 감정 기록 삭제하기"):
            delete_record(st.session_state.user_id, selected_day)
            st.success("감정 기록을 삭제했어요.")
            st.rerun()

    diary = load_diary(st.session_state.user_id, selected_day)

    if diary:
        st.markdown(f"### 📔 {selected_day}의 일반 일기")
        st.write(f"**{diary[0]}**")
        st.write(diary[1])

        if diary[2]:
            st.image(diary[2], caption="일기에 첨부한 사진")


# ------------------------------------------
# 11. 일반 일기 + 사진 첨부
# ------------------------------------------

def show_diary_page():
    st.header("📔 나의 일기장")
    st.write(
        "오늘 있었던 일, 기억하고 싶은 순간, 떠오르는 생각을 "
        "자유롭게 적어 보세요."
    )

    st.info(
        "날짜마다 일기 한 편을 저장할 수 있어요. "
        "사진은 한 장당 5MB 이하의 JPG, PNG, WEBP 파일을 지원해요."
    )

    user_id = st.session_state.user_id
    diary_list = load_diary_list(user_id)

    # 작성하거나 수정할 일기 날짜 선택
    diary_date = st.date_input(
        "일기 날짜",
        value=date.today(),
        key="diary_date"
    )

    existing = load_diary(user_id, diary_date)

    # 저장된 일기가 있으면 기존 내용을 불러옴
    if existing:
        default_title = existing[0]
        default_content = existing[1]
        existing_photo = existing[2]
        existing_mime = existing[3]
        updated_at = existing[4]

        st.success("이 날짜에 저장된 일기가 있어요. 수정할 수 있어요.")

        if existing_photo:
            st.markdown("#### 현재 첨부된 사진")
            st.image(existing_photo, use_container_width=True)
            st.caption(f"사진 형식: {existing_mime}")

            if st.button("현재 사진만 삭제하기"):
                delete_diary_photo(user_id, diary_date)
                st.success("사진을 삭제했어요. 일기 내용은 유지돼요.")
                st.rerun()

        st.caption(f"마지막 수정: {updated_at}")

    else:
        default_title = ""
        default_content = ""
        existing_photo = None
        existing_mime = None

    st.markdown("### ✏️ 일기 작성하기")

    with st.form("diary_form", clear_on_submit=False):
        title = st.text_input(
            "일기 제목",
            value=default_title,
            max_chars=100,
            placeholder="예: 친구와 함께한 즐거운 하루"
        )

        content = st.text_area(
            "오늘의 이야기",
            value=default_content,
            height=250,
            max_chars=10000,
            placeholder=(
                "오늘 무슨 일이 있었나요?\n"
                "기억하고 싶은 순간이나 생각을 자유롭게 적어 보세요."
            )
        )

        uploaded_photo = st.file_uploader(
            "사진 첨부하기 (선택 사항)",
            type=["jpg", "jpeg", "png", "webp"],
            help="휴대폰이나 컴퓨터에 저장된 사진을 선택할 수 있어요."
        )

        if uploaded_photo is not None:
            photo_bytes = uploaded_photo.getvalue()

            if len(photo_bytes) <= MAX_PHOTO_SIZE:
                st.markdown("#### 업로드한 사진 미리 보기")
                st.image(photo_bytes, use_container_width=True)
            else:
                st.error("사진은 한 장당 5MB 이하로 올려 주세요.")

        save_submitted = st.form_submit_button(
            "💾 일기 저장하기",
            use_container_width=True
        )

    if save_submitted:
        if not title.strip():
            st.error("일기 제목을 입력해 주세요.")
        elif not content.strip():
            st.error("일기 내용을 입력해 주세요.")
        elif (
            uploaded_photo is not None
            and len(uploaded_photo.getvalue()) > MAX_PHOTO_SIZE
        ):
            st.error("사진은 한 장당 5MB 이하로 올려 주세요.")
        else:
            success, message = save_diary(
                user_id,
                diary_date,
                title,
                content,
                uploaded_photo
            )

            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    # 저장된 일기 삭제
    if existing:
        st.divider()
        st.markdown("### 🗑️ 일기 관리")

        confirm_delete = st.checkbox(
            "이 일기를 삭제하겠습니다.",
            key=f"confirm_diary_delete_{diary_date}"
        )

        if st.button("일기 삭제하기", use_container_width=True):
            if confirm_delete:
                delete_diary(user_id, diary_date)
                st.success("일기와 첨부 사진을 삭제했어요.")
                st.rerun()
            else:
                st.warning("삭제하려면 먼저 확인 상자에 체크해 주세요.")

    # 지난 일기 목록
    st.divider()
    st.markdown("### 📚 지난 일기")

    diary_list = load_diary_list(user_id)

    if not diary_list:
        st.info("아직 작성한 일기가 없어요.")
    else:
        for saved_date, saved_title, saved_updated, has_photo in diary_list:
            photo_mark = " 📷" if has_photo else ""

            st.markdown(
                f"- **{saved_date}** — {saved_title}"
                f"{photo_mark}"
            )


# ------------------------------------------
# 12. 감정 처방전
# ------------------------------------------

def show_advice_page():
    st.header("🧸 감정 처방전")
    st.write(
        "병을 진단하는 것이 아니라, 마음을 돌보기 위한 "
        "작은 활동을 추천하는 공간이에요."
    )

    emotion = st.selectbox(
        "지금 내 마음과 가까운 날씨는?",
        list(EMOTIONS.keys()),
        format_func=lambda x: f"{EMOTIONS[x]['emoji']} {x}"
    )

    st.markdown(
        "<div class='weather-banner'>"
        f"<h2>{EMOTIONS[emotion]['emoji']} {emotion} 날씨 처방전</h2>"
        f"<p>{EMOTIONS[emotion]['description']}</p>"
        "<p>감정을 억지로 바꾸지 않아도 괜찮아요. "
        "할 수 있는 작은 행동부터 골라 봐요.</p>"
        "</div>",
        unsafe_allow_html=True
    )

    st.subheader("오늘 실천해 볼 활동")

    for i, activity in enumerate(ADVICE[emotion], start=1):
        st.checkbox(
            f"{i}. {activity}",
            key=f"advice_{emotion}_{i}"
        )

    st.caption(
        "힘든 감정이 오래 지속되거나 일상생활이 어렵다면 "
        "믿을 만한 어른이나 상담 전문가에게 도움을 요청해 보세요."
    )


# ------------------------------------------
# 13. 감정 표현 연습실
# ------------------------------------------

def show_expression_page():
    st.header("💬 감정 표현 연습실")
    st.write(
        "어떤 일이 있었는지, 무엇을 느꼈는지, "
        "나에게 무엇이 필요한지 문장으로 만들어 봐요."
    )

    examples = {
        "짜증 나": [
            "내 말을 끝까지 들어 주지 않아서 답답했어.",
            "계획이 갑자기 바뀌어서 당황스러웠어."
        ],
        "슬퍼": [
            "친구와 함께하지 못해서 외로웠어.",
            "기대했던 일이 잘되지 않아 속상했어."
        ],
        "불안해": [
            "발표할 때 실수할까 봐 걱정돼.",
            "결과를 아직 몰라서 마음이 조급해."
        ],
        "화가 나": [
            "내 입장을 설명할 기회가 없어서 화가 났어.",
            "약속이 지켜지지 않아 실망스럽고 화가 나."
        ],
        "좋아": [
            "내 노력을 알아봐 줘서 뿌듯했어.",
            "친구와 즐거운 시간을 보내서 행복했어."
        ],
        "모르겠어": [
            "무슨 감정인지 잘 모르겠지만 마음이 복잡해.",
            "지금은 혼자 생각할 시간이 필요해."
        ]
    }

    selected = st.selectbox("표현해 보고 싶은 감정", list(examples.keys()))

    st.markdown("### 문장 예시")

    for example in examples[selected]:
        st.info(example)

    st.markdown("### 나만의 감정 문장 만들기")

    situation = st.text_input(
        "1. 어떤 일이 있었나요?",
        placeholder="예: 친구가 내 이야기를 듣지 않았다."
    )

    feeling = st.text_input(
        "2. 어떤 감정을 느꼈나요?",
        placeholder="예: 서운하고 답답했다."
    )

    need = st.text_input(
        "3. 나에게 무엇이 필요했나요?",
        placeholder="예: 내 이야기를 끝까지 들어 주는 것"
    )

    if st.button("나의 감정 문장 만들기", use_container_width=True):
        if situation.strip() and feeling.strip() and need.strip():
            st.success(
                f"'{situation.strip()}'라는 일이 있었을 때, "
                f"나는 '{feeling.strip()}'을 느꼈어. "
                f"나에게는 '{need.strip()}'이 필요했어."
            )
        else:
            st.warning("세 가지 질문에 모두 답해 주세요.")


# ------------------------------------------
# 14. 감정 변화 분석 그래프
# ------------------------------------------

def show_analysis_page(df):
    st.header("📈 감정 변화 분석")
    st.write("날짜에 따라 감정 점수와 스트레스 점수를 비교해 봐요.")

    if df.empty:
        st.info("아직 감정 기록이 없어요.")
        return

    col1, col2 = st.columns(2)

    with col1:
        start_date = st.date_input(
            "분석 시작 날짜",
            value=date.today().replace(day=1),
            key="analysis_start"
        )

    with col2:
        end_date = st.date_input(
            "분석 종료 날짜",
            value=date.today(),
            key="analysis_end"
        )

    if start_date > end_date:
        st.error("시작 날짜는 종료 날짜보다 늦을 수 없어요.")
        return

    filtered = df[
        (df["record_date"].dt.date >= start_date)
        & (df["record_date"].dt.date <= end_date)
    ].copy()

    if filtered.empty:
        st.info("선택한 기간에는 기록이 없어요.")
        return

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=filtered["record_date"],
        y=filtered["emotion_score"],
        mode="lines+markers",
        name="감정 점수",
        line=dict(color="#E7A55B", width=3)
    ))

    fig.add_trace(go.Scatter(
        x=filtered["record_date"],
        y=filtered["stress"],
        mode="lines+markers",
        name="스트레스",
        line=dict(color="#8E9EC9", width=3)
    ))

    fig.update_layout(
        paper_bgcolor="#FFF9F0",
        plot_bgcolor="#FFFFFF",
        font=dict(color="#51483F"),
        xaxis_title="날짜",
        yaxis_title="점수",
        yaxis=dict(range=[0, 10], dtick=1),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.12)
    )

    st.plotly_chart(fig, use_container_width=True)

    col1, col2, col3 = st.columns(3)

    col1.metric("기록한 날", f"{len(filtered)}일")
    col2.metric("평균 스트레스", f"{filtered['stress'].mean():.1f} / 10")
    col3.metric(
        "감정 점수 평균",
        f"{filtered['emotion_score'].mean():.1f} / 5"
    )

    st.markdown("### 감정별 기록 횟수")

    emotion_counts = (
        filtered["emotion"]
        .value_counts()
        .reindex(EMOTIONS.keys(), fill_value=0)
    )

    count_fig = go.Figure(go.Bar(
        x=[
            f"{EMOTIONS[e]['emoji']} {e}"
            for e in emotion_counts.index
        ],
        y=emotion_counts.values,
        marker_color="#E9BC86"
    ))

    count_fig.update_layout(
        paper_bgcolor="#FFF9F0",
        plot_bgcolor="#FFFFFF",
        font=dict(color="#51483F"),
        xaxis_title="감정 날씨",
        yaxis_title="기록 횟수"
    )

    st.plotly_chart(count_fig, use_container_width=True)

    st.caption(
        "감정 점수는 변화를 보기 위한 참고용 값이에요. "
        "두 선이 함께 움직여도 한 감정이 다른 감정을 "
        "일으켰다고 단정할 수는 없어요."
    )


# ------------------------------------------
# 15. 한 달 감정 연구 보고서
# ------------------------------------------

def show_report_page(df):
    st.header("📒 감정 연구 보고서")
    st.write("한 달 동안 기록한 마음의 날씨를 정리해 봐요.")

    today = date.today()

    col1, col2 = st.columns(2)

    with col1:
        year = st.selectbox(
            "보고서 연도",
            list(range(today.year - 5, today.year + 1)),
            index=5,
            key="report_year"
        )

    with col2:
        month = st.selectbox(
            "보고서 월",
            list(range(1, 13)),
            index=today.month - 1,
            key="report_month"
        )

    month_df = df[
        (df["record_date"].dt.year == year)
        & (df["record_date"].dt.month == month)
    ].copy()

    if month_df.empty:
        st.info(
            f"{year}년 {month}월에는 기록이 없어요. "
            "감정 날씨를 기록하면 보고서를 만들 수 있어요."
        )
        return

    total_days = len(month_df)
    avg_stress = month_df["stress"].mean()
    counts = month_df["emotion"].value_counts()
    most_emotion = counts.index[0]

    col1, col2, col3 = st.columns(3)

    col1.metric("기록한 날", f"{total_days}일")
    col2.metric("평균 스트레스", f"{avg_stress:.1f} / 10")
    col3.metric(
        "가장 자주 기록한 감정",
        f"{EMOTIONS[most_emotion]['emoji']} {most_emotion}"
    )

    st.markdown("### 이번 달 감정 기록")

    for emotion, info in EMOTIONS.items():
        count = int(counts.get(emotion, 0))

        if count > 0:
            st.write(f"{info['emoji']} **{emotion}**: {count}회")
            st.progress(count / total_days)

    highest = month_df.loc[month_df["stress"].idxmax()]
    lowest = month_df.loc[month_df["stress"].idxmin()]

    st.markdown("### 나의 감정 돌아보기")

    st.write(
        f"- 스트레스가 가장 높았던 날: "
        f"{highest['record_date'].strftime('%m월 %d일')} "
        f"({highest['stress']}점)"
    )

    st.write(
        f"- 스트레스가 가장 낮았던 날: "
        f"{lowest['record_date'].strftime('%m월 %d일')} "
        f"({lowest['stress']}점)"
    )

    st.markdown("### 한 달 돌아보기")

    reflection = st.text_area(
        "이번 달을 돌아보며 느낀 점",
        placeholder="기억하고 싶은 일이나 다음 달의 목표를 적어 보세요.",
        max_chars=1000
    )

    # 감정 기록을 CSV로 다운로드
    export_df = month_df[
        ["record_date", "emotion", "reason", "stress"]
    ].copy()

    export_df["record_date"] = (
        export_df["record_date"].dt.strftime("%Y-%m-%d")
    )

    export_df = export_df.rename(columns={
        "record_date": "날짜",
        "emotion": "감정 날씨",
        "reason": "감정 이유",
        "stress": "스트레스 점수"
    })

    st.download_button(
        "📥 감정 기록 다운로드 (CSV)",
        data=export_df.to_csv(index=False, encoding="utf-8-sig"),
        file_name=f"감정연구보고서_{year}_{month:02d}.csv",
        mime="text/csv",
        use_container_width=True
    )

    if reflection.strip():
        st.markdown("### 나의 한 달 돌아보기")
        st.info(reflection)

    # 같은 기간의 일반 일기도 함께 확인
    diaries = [
        item for item in load_diary_list(st.session_state.user_id)
        if datetime.strptime(item[0], "%Y-%m-%d").year == year
        and datetime.strptime(item[0], "%Y-%m-%d").month == month
    ]

    st.markdown("### 이번 달 일반 일기")
    if diaries:
        for diary_date, diary_title, updated_at, has_photo in diaries:
            photo_mark = " 📷" if has_photo else ""
            st.write(f"- {diary_date}: {diary_title}{photo_mark}")
    else:
        st.caption("이번 달에 작성한 일반 일기가 없어요.")

    st.caption(
        "이 보고서는 기록을 요약하는 기능이며, "
        "정신건강 상태를 진단하지 않아요."
    )


# ------------------------------------------
# 16. 로그인 후 메인 화면
# ------------------------------------------

def show_main_app():
    # 현재 로그인한 사용자의 감정 기록만 불러오기
    df = load_records(st.session_state.user_id)

    st.markdown(
        "<div class='weather-banner'>"
        "<h1>🌦️ 감정날씨 연구소</h1>"
        "<p>내 마음의 날씨를 관찰하고, 하루의 이야기를 기록해요.</p>"
        "</div>",
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.markdown("## 🌷 메뉴")
        st.write(f"안녕하세요, **{st.session_state.username}** 연구원님!")

        menu = st.radio(
            "원하는 기능을 선택해 주세요.",
            [
                "오늘의 감정 날씨",
                "일반 일기",
                "감정 달력",
                "감정 처방전",
                "감정 표현 연습실",
                "감정 변화 분석",
                "감정 연구 보고서"
            ]
        )

        st.divider()
        st.caption("오늘도 내 마음을 천천히 살펴봐요.")

        if st.button("로그아웃", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.username = None
            st.rerun()

    if menu == "오늘의 감정 날씨":
        show_today_page(df)

    elif menu == "일반 일기":
        show_diary_page()

    elif menu == "감정 달력":
        show_calendar_page(df)

    elif menu == "감정 처방전":
        show_advice_page()

    elif menu == "감정 표현 연습실":
        show_expression_page()

    elif menu == "감정 변화 분석":
        show_analysis_page(df)

    elif menu == "감정 연구 보고서":
        show_report_page(df)


# ------------------------------------------
# 17. 프로그램 시작
# ------------------------------------------

if st.session_state.user_id is None:
    show_login_page()
else:
    show_main_app()
