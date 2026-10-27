
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import calendar
import os
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash


# ==========================================
# 1. 기본 설정
# ==========================================

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
    "안개": {"score": 3, "emoji": "🌫️"},
    "비": {"score": 2, "emoji": "🌧️"},
    "번개": {"score": 1, "emoji": "⛈️"},
}

EMOTION_ADVICE = {
    "맑음": "오늘 기분이 좋았다면 그 이유를 기록해 보세요. 즐거웠던 순간을 기억하는 데 도움이 됩니다.",
    "무지개": "여러 감정이 함께 느껴졌을 수 있어요. 기뻤던 점과 아쉬웠던 점을 나누어 적어 보세요.",
    "구름 조금": "조금 복잡한 마음이 들었다면 잠깐 쉬면서 지금 느끼는 감정을 살펴보세요.",
    "흐림": "기분이 가라앉을 때는 좋아하는 음악을 듣거나 편안한 활동을 해 보세요.",
    "안개": "감정이 무엇인지 정확히 알기 어려울 수 있어요. '답답하다', '복잡하다'처럼 가까운 단어부터 찾아보세요.",
    "비": "속상한 감정도 자연스러운 감정이에요. 믿을 수 있는 사람에게 마음을 이야기해 보세요.",
    "번개": "감정이 강하게 느껴질 때는 잠시 멈추고 천천히 호흡해 보세요. 안전하고 편안한 장소에서 쉬어도 좋아요.",
}


# ==========================================
# 2. 데이터베이스
# ==========================================

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS emotion_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                record_date TEXT NOT NULL,
                weather TEXT NOT NULL,
                reason TEXT,
                stress INTEGER DEFAULT 3,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, record_date),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                diary_date TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                photo_data BLOB,
                photo_mime TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, diary_date),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)

        conn.commit()


init_db()


# ==========================================
# 3. 공통 함수
# ==========================================

def get_user_id():
    return st.session_state.get("user_id")


def get_emotion_record(user_id, selected_date):
    with get_connection() as conn:
        return conn.execute("""
            SELECT weather, reason, stress
            FROM emotion_records
            WHERE user_id = ? AND record_date = ?
        """, (user_id, selected_date)).fetchone()


def get_diary(user_id, selected_date):
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, diary_date, title, content, photo_data, photo_mime
            FROM diaries
            WHERE user_id = ? AND diary_date = ?
        """, (user_id, selected_date)).fetchone()


def get_all_diaries(user_id):
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, diary_date, title, content, photo_data, photo_mime
            FROM diaries
            WHERE user_id = ?
            ORDER BY diary_date DESC
        """, (user_id,)).fetchall()


def save_diary(user_id, diary_date, title, content, photo_bytes, photo_mime):
    existing = get_diary(user_id, diary_date)

    with get_connection() as conn:
        if existing:
            # 새 사진을 올리지 않으면 기존 사진을 유지합니다.
            if photo_bytes is None:
                conn.execute("""
                    UPDATE diaries
                    SET title = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND diary_date = ?
                """, (title, content, user_id, diary_date))
            else:
                conn.execute("""
                    UPDATE diaries
                    SET title = ?, content = ?, photo_data = ?,
                        photo_mime = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND diary_date = ?
                """, (
                    title, content, photo_bytes, photo_mime,
                    user_id, diary_date
                ))
        else:
            conn.execute("""
                INSERT INTO diaries
                (user_id, diary_date, title, content, photo_data, photo_mime)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_id, diary_date, title, content,
                photo_bytes, photo_mime
            ))

        conn.commit()


def delete_diary_photo(user_id, diary_date):
    with get_connection() as conn:
        conn.execute("""
            UPDATE diaries
            SET photo_data = NULL, photo_mime = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND diary_date = ?
        """, (user_id, diary_date))
        conn.commit()


def delete_diary(user_id, diary_date):
    with get_connection() as conn:
        conn.execute("""
            DELETE FROM diaries
            WHERE user_id = ? AND diary_date = ?
        """, (user_id, diary_date))
        conn.commit()

    if st.session_state.get("selected_diary_date") == diary_date:
        st.session_state.selected_diary_date = None


# ==========================================
# 4. 화면 디자인
# ==========================================

st.markdown("""
<style>
    .stApp {
        background-color: #FFF9F0;
    }

    h1, h2, h3 {
        color: #65534A;
    }

    .subtitle {
        color: #89776B;
        font-size: 17px;
    }

    .weather-card {
        background-color: #FFFFFF;
        border: 1px solid #F0E2D3;
        border-radius: 15px;
        padding: 18px;
        margin-bottom: 12px;
    }

    .diary-card {
        background-color: #FFFFFF;
        border: 1px solid #EADBCB;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 12px;
    }

    div.stButton > button {
        border-radius: 10px;
        border: 1px solid #E8D7C5;
        background-color: #FFFFFF;
        color: #65534A;
    }

    div.stButton > button:hover {
        background-color: #FCEBD8;
        border-color: #D8B99A;
        color: #65534A;
    }

    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 12px;
        border: 1px solid #F0E2D3;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 5. 회원가입 및 로그인
# ==========================================

def show_login_page():
    st.title("🌦️ 감정날씨 연구소")
    st.markdown(
        '<p class="subtitle">오늘의 마음을 날씨처럼 기록해 보세요.</p>',
        unsafe_allow_html=True
    )

    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

    with tab_login:
        st.subheader("다시 만나서 반가워요!")

        login_username = st.text_input(
            "아이디",
            key="login_username"
        )
        login_password = st.text_input(
            "비밀번호",
            type="password",
            key="login_password"
        )

        if st.button("로그인", key="login_button", use_container_width=True):
            with get_connection() as conn:
                user = conn.execute("""
                    SELECT id, username, password_hash
                    FROM users
                    WHERE username = ?
                """, (login_username.strip(),)).fetchone()

            if user and check_password_hash(user[2], login_password):
                st.session_state.user_id = user[0]
                st.session_state.username = user[1]
                st.session_state.selected_diary_date = None
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호를 확인해 주세요.")

    with tab_signup:
        st.subheader("새 계정 만들기")

        signup_username = st.text_input(
            "사용할 아이디",
            key="signup_username"
        )
        signup_password = st.text_input(
            "사용할 비밀번호",
            type="password",
            key="signup_password"
        )
        signup_password_confirm = st.text_input(
            "비밀번호 확인",
            type="password",
            key="signup_password_confirm"
        )

        if st.button("회원가입", key="signup_button", use_container_width=True):
            username = signup_username.strip()

            if not username or not signup_password:
                st.warning("아이디와 비밀번호를 모두 입력해 주세요.")
            elif len(username) < 3:
                st.warning("아이디는 3글자 이상으로 입력해 주세요.")
            elif len(signup_password) < 4:
                st.warning("비밀번호는 4글자 이상으로 입력해 주세요.")
            elif signup_password != signup_password_confirm:
                st.error("비밀번호가 서로 다릅니다.")
            else:
                try:
                    hashed = generate_password_hash(signup_password)

                    with get_connection() as conn:
                        conn.execute("""
                            INSERT INTO users (username, password_hash)
                            VALUES (?, ?)
                        """, (username, hashed))
                        conn.commit()

                    st.success("회원가입이 완료되었습니다. 로그인해 주세요.")

                except sqlite3.IntegrityError:
                    st.error("이미 사용 중인 아이디입니다.")


# ==========================================
# 6. 오늘의 감정 날씨 기록
# ==========================================

def show_emotion_page(user_id):
    st.header("☀️ 오늘의 감정 날씨")
    st.write("오늘 내 마음은 어떤 날씨였나요?")

    selected_date = st.date_input(
        "기록할 날짜",
        value=date.today(),
        key="emotion_date"
    )
    date_text = selected_date.isoformat()

    existing = get_emotion_record(user_id, date_text)

    default_weather = existing[0] if existing else "맑음"
    default_reason = existing[1] if existing else ""
    default_stress = existing[2] if existing else 3

    weather_list = list(WEATHER_OPTIONS.keys())

    weather = st.selectbox(
        "오늘의 감정 날씨",
        weather_list,
        index=weather_list.index(default_weather)
        if default_weather in weather_list else 0,
        format_func=lambda x: f"{WEATHER_OPTIONS[x]['emoji']} {x}",
        key=f"weather_{date_text}"
    )

    reason = st.text_area(
        "그렇게 느낀 이유는 무엇인가요?",
        value=default_reason or "",
        placeholder="오늘 있었던 일이나 마음에 남은 순간을 적어 보세요.",
        key=f"reason_{date_text}"
    )

    stress = st.slider(
        "오늘의 스트레스 정도",
        min_value=1,
        max_value=5,
        value=int(default_stress or 3),
        help="1은 매우 낮음, 5는 매우 높음입니다.",
        key=f"stress_{date_text}"
    )

    st.caption("스트레스 정도: 1 매우 낮음 · 2 낮음 · 3 보통 · 4 높음 · 5 매우 높음")

    if st.button("감정 날씨 저장하기", use_container_width=True):
        with get_connection() as conn:
            conn.execute("""
                INSERT INTO emotion_records
                (user_id, record_date, weather, reason, stress)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, record_date)
                DO UPDATE SET
                    weather = excluded.weather,
                    reason = excluded.reason,
                    stress = excluded.stress
            """, (user_id, date_text, weather, reason, stress))
            conn.commit()

        st.success("오늘의 감정 날씨를 저장했어요!")
        st.rerun()

    st.divider()
    st.subheader("오늘의 감정 처방")

    st.markdown(
        f"### {WEATHER_OPTIONS[weather]['emoji']} {weather}"
    )
    st.write(EMOTION_ADVICE[weather])


# ==========================================
# 7. 일기 쓰기 및 지난 일기 바로 보기
# ==========================================

def show_diary_page(user_id):
    st.header("📔 나의 일기")
    st.write("오늘 있었던 일과 마음을 자유롭게 기록해 보세요.")

    all_diaries = get_all_diaries(user_id)

    # --------------------------------------
    # 지난 일기 목록
    # --------------------------------------
    st.subheader("🗂️ 지난 일기")
    st.caption("날짜 또는 제목을 누르면 해당 일기의 내용이 바로 열립니다.")

    if not all_diaries:
        st.info("아직 작성한 일기가 없어요. 첫 번째 일기를 작성해 보세요!")
    else:
        for diary in all_diaries:
            diary_id, diary_date, diary_title = diary[0], diary[1], diary[2]

            date_col, title_col = st.columns([1, 3])

            # 날짜 버튼을 눌러도 해당 일기가 열립니다.
            with date_col:
                if st.button(
                    f"📅 {diary_date}",
                    key=f"open_diary_date_{diary_id}",
                    use_container_width=True
                ):
                    st.session_state.selected_diary_date = diary_date
                    st.rerun()

            # 제목 버튼을 눌러도 같은 일기가 열립니다.
            with title_col:
                if st.button(
                    f"📖 {diary_title}",
                    key=f"open_diary_title_{diary_id}",
                    use_container_width=True
                ):
                    st.session_state.selected_diary_date = diary_date
                    st.rerun()

    # --------------------------------------
    # 선택한 지난 일기 표시
    # --------------------------------------
    selected_date = st.session_state.get("selected_diary_date")

    if selected_date:
        selected_diary = get_diary(user_id, selected_date)

        if selected_diary:
            st.divider()
            st.subheader("📖 선택한 일기")

            st.markdown(
                f"### {selected_diary[2]}"
            )
            st.caption(f"작성 날짜: {selected_diary[1]}")

            st.markdown(
                '<div class="diary-card">',
                unsafe_allow_html=True
            )
            st.write(selected_diary[3])
            st.markdown("</div>", unsafe_allow_html=True)

            # 선택한 일기에 사진이 있으면 함께 표시합니다.
            if selected_diary[4]:
                image_col, _ = st.columns([1, 2])
                with image_col:
                    st.image(
                        selected_diary[4],
                        width=DIARY_PHOTO_WIDTH,
                        caption="일기에 첨부한 사진"
                    )

            close_col, edit_col, delete_col = st.columns(3)

            with close_col:
                if st.button(
                    "닫기",
                    key="close_selected_diary",
                    use_container_width=True
                ):
                    st.session_state.selected_diary_date = None
                    st.rerun()

            with edit_col:
                if st.button(
                    "이 일기 수정하기",
                    key="edit_selected_diary",
                    use_container_width=True
                ):
                    st.session_state.diary_edit_date = selected_date
                    st.session_state.diary_form_date = date.fromisoformat(
                        selected_date
                    )
                    st.rerun()

            with delete_col:
                if st.button(
                    "이 일기 삭제하기",
                    key="delete_selected_diary",
                    use_container_width=True
                ):
                    st.session_state.confirm_delete_diary = selected_date
                    st.rerun()

    # 삭제 확인은 실수로 기록을 지우는 것을 방지합니다.
    confirm_delete = st.session_state.get("confirm_delete_diary")

    if confirm_delete:
        st.warning(f"{confirm_delete} 일기를 정말 삭제할까요?")
        yes_col, no_col = st.columns(2)

        with yes_col:
            if st.button("삭제하기", key="confirm_delete_yes"):
                delete_diary(user_id, confirm_delete)
                st.session_state.confirm_delete_diary = None
                st.success("일기를 삭제했습니다.")
                st.rerun()

        with no_col:
            if st.button("취소", key="confirm_delete_no"):
                st.session_state.confirm_delete_diary = None
                st.rerun()

    st.divider()

    # --------------------------------------
    # 새 일기 작성 또는 기존 일기 수정
    # --------------------------------------
    edit_date = st.session_state.get("diary_edit_date")

    if edit_date:
        st.subheader("✏️ 일기 수정하기")
        initial_date = date.fromisoformat(edit_date)
        existing = get_diary(user_id, edit_date)
    else:
        st.subheader("✍️ 새 일기 쓰기")
        initial_date = st.session_state.get(
            "diary_form_date", date.today()
        )
        existing = get_diary(user_id, initial_date.isoformat())

    with st.form("diary_form", clear_on_submit=False):
        diary_date = st.date_input(
            "일기 날짜",
            value=initial_date,
            key="diary_input_date"
        )

        default_title = existing[2] if existing else ""
        default_content = existing[3] if existing else ""

        title = st.text_input(
            "일기 제목",
            value=default_title,
            placeholder="예: 오늘 있었던 특별한 일",
            key=f"diary_title_{initial_date.isoformat()}"
        )

        content = st.text_area(
            "일기 내용",
            value=default_content,
            height=200,
            placeholder="오늘 있었던 일, 느낀 감정, 기억하고 싶은 순간을 적어 보세요.",
            key=f"diary_content_{initial_date.isoformat()}"
        )

        uploaded_photo = st.file_uploader(
            "사진 첨부하기 (선택)",
            type=["jpg", "jpeg", "png", "webp"],
            help="사진은 최대 5MB까지 첨부할 수 있습니다.",
            key=f"diary_photo_{initial_date.isoformat()}"
        )

        submitted = st.form_submit_button(
            "일기 저장하기",
            use_container_width=True
        )

    # 현재 저장된 사진 표시
    if existing and existing[4]:
        st.caption("현재 저장된 사진")
        image_col, _ = st.columns([1, 2])
        with image_col:
            st.image(
                existing[4],
                width=DIARY_PHOTO_WIDTH
            )

        if st.button(
            "현재 사진 삭제하기",
            key=f"remove_photo_{initial_date.isoformat()}"
        ):
            delete_diary_photo(user_id, initial_date.isoformat())
            st.success("사진을 삭제했습니다.")
            st.rerun()

    # 업로드한 사진 미리 보기
    photo_bytes = None
    photo_mime = None

    if uploaded_photo is not None:
        photo_bytes = uploaded_photo.getvalue()
        photo_mime = uploaded_photo.type

        if len(photo_bytes) > MAX_PHOTO_SIZE:
            st.error("사진 크기가 5MB를 초과합니다. 더 작은 사진을 선택해 주세요.")
            photo_bytes = None
            photo_mime = None
        else:
            st.caption("업로드한 사진 미리 보기")
            image_col, _ = st.columns([1, 2])
            with image_col:
                st.image(
                    photo_bytes,
                    width=DIARY_PHOTO_WIDTH
                )

    if submitted:
        if not title.strip():
            st.warning("일기 제목을 입력해 주세요.")
        elif not content.strip():
            st.warning("일기 내용을 입력해 주세요.")
        elif uploaded_photo is not None and len(uploaded_photo.getvalue()) > MAX_PHOTO_SIZE:
            st.error("사진 크기가 5MB를 초과합니다.")
        else:
            save_diary(
                user_id,
                diary_date.isoformat(),
                title.strip(),
                content.strip(),
                photo_bytes,
                photo_mime
            )

            st.session_state.selected_diary_date = diary_date.isoformat()
            st.session_state.diary_edit_date = None
            st.session_state.diary_form_date = date.today()

            st.success("일기를 저장했습니다.")
            st.rerun()

    if edit_date:
        if st.button("수정 취소", key="cancel_diary_edit"):
            st.session_state.diary_edit_date = None
            st.session_state.diary_form_date = date.today()
            st.rerun()


# ==========================================
# 8. 감정 달력
# ==========================================

def show_calendar_page(user_id):
    st.header("🗓️ 감정 달력")
    st.write("날짜별 감정과 일기를 한눈에 확인할 수 있어요.")

    today = date.today()

    year_col, month_col = st.columns(2)

    with year_col:
        year = st.selectbox(
            "연도",
            list(range(today.year - 5, today.year + 2)),
            index=5
        )

    with month_col:
        month = st.selectbox(
            "월",
            list(range(1, 13)),
            index=today.month - 1
        )

    with get_connection() as conn:
        emotion_rows = conn.execute("""
            SELECT record_date, weather
            FROM emotion_records
            WHERE user_id = ?
            AND substr(record_date, 1, 7) = ?
        """, (user_id, f"{year:04d}-{month:02d}")).fetchall()

        diary_rows = conn.execute("""
            SELECT diary_date, title, content, photo_data
            FROM diaries
            WHERE user_id = ?
            AND substr(diary_date, 1, 7) = ?
        """, (user_id, f"{year:04d}-{month:02d}")).fetchall()

    emotions = {row[0]: row[1] for row in emotion_rows}
    diaries = {row[0]: row for row in diary_rows}

    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdayscalendar(year, month)

    cols = st.columns(7)
    for col, name in zip(cols, ["일", "월", "화", "수", "목", "금", "토"]):
        col.markdown(f"**{name}**")

    for week in weeks:
        cols = st.columns(7)

        for col, day in zip(cols, week):
            with col:
                if day == 0:
                    st.write(" ")
                    continue

                day_date = date(year, month, day).isoformat()
                weather = emotions.get(day_date)
                diary = diaries.get(day_date)

                label = f"**{day}**"

                if weather:
                    emoji = WEATHER_OPTIONS.get(
                        weather, {"emoji": "🌦️"}
                    )["emoji"]
                    label += f"\n{emoji}"

                if diary:
                    label += "\n📔"

                st.markdown(label)

                if weather:
                    st.caption(weather)

                if diary:
                    if st.button(
                        "일기 보기",
                        key=f"calendar_diary_{day_date}",
                        use_container_width=True
                    ):
                        st.session_state.selected_diary_date = day_date
                        st.session_state.page = "나의 일기"
                        st.rerun()

                    if diary[3]:
                        st.image(
                            diary[3],
                            width=CALENDAR_PHOTO_WIDTH
                        )

    st.caption("☀️ 맑음 · 🌈 무지개 · 🌤️ 구름 조금 · ☁️ 흐림 · 🌫️ 안개 · 🌧️ 비 · ⛈️ 번개")
    st.caption("📔 표시가 있는 날짜에는 일기가 저장되어 있습니다.")


# ==========================================
# 9. 감정 표현 연습
# ==========================================

def show_expression_page():
    st.header("💬 감정 표현 연습")
    st.write("감정을 구체적인 말로 표현하는 연습을 해 보세요.")

    situations = {
        "친구가 약속을 지키지 않았을 때": [
            "나는 약속을 지키지 않아서 속상했어.",
            "다음에는 미리 알려 주면 좋겠어."
        ],
        "발표를 앞두고 긴장될 때": [
            "나는 발표를 잘할 수 있을지 걱정돼.",
            "천천히 준비하고 연습해 보고 싶어."
        ],
        "친구가 나를 칭찬했을 때": [
            "네가 칭찬해 줘서 기뻤어.",
            "내 노력을 알아줘서 고마워."
        ],
        "혼자 있고 싶을 때": [
            "지금은 혼자 생각할 시간이 필요해.",
            "조금 쉬고 나서 다시 이야기하고 싶어."
        ],
        "도움이 필요할 때": [
            "지금 혼자 해결하기 어려워.",
            "이 부분을 함께 살펴봐 줄 수 있어?"
        ],
    }

    situation = st.selectbox("상황 선택하기", list(situations.keys()))

    st.subheader("이렇게 표현해 볼 수 있어요")
    for sentence in situations[situation]:
        st.info(sentence)

    st.subheader("나만의 표현 만들기")
    my_expression = st.text_area(
        "내 감정을 담아 문장을 만들어 보세요.",
        placeholder="나는 ______해서 ______한 기분이 들었어."
    )

    if my_expression.strip():
        st.success("좋아요. 내 감정을 구체적인 말로 표현해 보았어요.")


# ==========================================
# 10. 감정 변화 분석
# ==========================================

def show_analysis_page(user_id):
    st.header("📊 감정 변화 분석")
    st.write("기록한 감정 날씨와 스트레스 정도의 변화를 살펴보세요.")

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT record_date, weather, stress, reason
            FROM emotion_records
            WHERE user_id = ?
            ORDER BY record_date
        """, (user_id,)).fetchall()

    if not rows:
        st.info("분석할 기록이 아직 없어요. 감정 날씨를 먼저 기록해 보세요.")
        return

    df = pd.DataFrame(
        rows,
        columns=["날짜", "감정 날씨", "스트레스", "이유"]
    )

    df["날짜"] = pd.to_datetime(df["날짜"])
    df["감정 점수"] = df["감정 날씨"].map(
        lambda x: WEATHER_OPTIONS.get(x, {"score": 3})["score"]
    )

    min_date = df["날짜"].min().date()
    max_date = df["날짜"].max().date()

    start_date, end_date = st.date_input(
        "분석 기간",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    ) if min_date != max_date else (min_date, max_date)

    filtered = df[
        (df["날짜"].dt.date >= start_date)
        & (df["날짜"].dt.date <= end_date)
    ].copy()

    if filtered.empty:
        st.info("선택한 기간에 기록이 없습니다.")
        return

    average_emotion = filtered["감정 점수"].mean()
    average_stress = filtered["스트레스"].mean()

    metric1, metric2, metric3 = st.columns(3)

    metric1.metric("기록한 날", f"{len(filtered)}일")
    metric2.metric("평균 감정 점수", f"{average_emotion:.1f} / 5")
    metric3.metric("평균 스트레스", f"{average_stress:.1f} / 5")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=filtered["날짜"],
        y=filtered["감정 점수"],
        mode="lines+markers",
        name="감정 점수",
        line=dict(width=3),
        hovertemplate="%{x|%Y-%m-%d}<br>감정 점수: %{y}<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=filtered["날짜"],
        y=filtered["스트레스"],
        mode="lines+markers",
        name="스트레스",
        line=dict(width=3, dash="dash"),
        hovertemplate="%{x|%Y-%m-%d}<br>스트레스: %{y}<extra></extra>"
    ))

    fig.update_layout(
        title="날짜별 감정과 스트레스 변화",
        xaxis_title="날짜",
        yaxis_title="점수 (1~5)",
        yaxis=dict(range=[0, 5.5], dtick=1),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFF9F0"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("기록 돌아보기")
    st.dataframe(
        filtered[["날짜", "감정 날씨", "감정 점수", "스트레스", "이유"]],
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "감정 점수는 기록한 감정 날씨를 바탕으로 만든 간단한 지표입니다. "
        "감정이나 스트레스의 원인을 확정적으로 판단하는 자료는 아닙니다."
    )


# ==========================================
# 11. 월간 감정 연구 보고서
# ==========================================

def show_monthly_report(user_id):
    st.header("🔎 월간 감정 연구 보고서")
    st.write("한 달 동안의 감정 기록을 요약해 보세요.")

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

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT record_date, weather, reason, stress
            FROM emotion_records
            WHERE user_id = ?
            AND substr(record_date, 1, 7) = ?
            ORDER BY record_date
        """, (user_id, f"{year:04d}-{month:02d}")).fetchall()

        diary_count = conn.execute("""
            SELECT COUNT(*)
            FROM diaries
            WHERE user_id = ?
            AND substr(diary_date, 1, 7) = ?
        """, (user_id, f"{year:04d}-{month:02d}")).fetchone()[0]

    if not rows and diary_count == 0:
        st.info("선택한 달에는 아직 기록이 없습니다.")
        return

    df = pd.DataFrame(
        rows,
        columns=["날짜", "감정 날씨", "이유", "스트레스"]
    )

    st.subheader(f"📅 {year}년 {month}월 기록 요약")

    col1, col2, col3 = st.columns(3)
    col1.metric("감정 기록", f"{len(df)}일")
    col2.metric("작성한 일기", f"{diary_count}개")

    if not df.empty:
        col3.metric("평균 스트레스", f"{df['스트레스'].mean():.1f} / 5")

        weather_counts = df["감정 날씨"].value_counts()
        most_common = weather_counts.index[0]

        st.markdown("### 가장 자주 기록한 감정 날씨")
        st.write(
            f"{WEATHER_OPTIONS[most_common]['emoji']} **{most_common}** "
            f"({int(weather_counts.iloc[0])}회)"
        )

        fig = go.Figure(data=[
            go.Bar(
                x=weather_counts.index,
                y=weather_counts.values,
                text=weather_counts.values,
                textposition="auto"
            )
        ])

        fig.update_layout(
            title="감정 날씨별 기록 횟수",
            xaxis_title="감정 날씨",
            yaxis_title="기록 횟수",
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFF9F0"
        )

        st.plotly_chart(fig, use_container_width=True)

        st.markdown("### 이번 달 기록")
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### 스스로 돌아볼 질문")
        st.write("- 이번 달에 가장 자주 느낀 감정은 무엇이었나요?")
        st.write("- 기분이 좋아졌던 날에는 어떤 일이 있었나요?")
        st.write("- 스트레스가 높았던 날에 나에게 도움이 된 것은 무엇이었나요?")
        st.write("- 다음 달에는 어떤 감정 표현을 연습해 보고 싶나요?")


# ==========================================
# 12. 메인 화면 및 메뉴
# ==========================================

def show_main_app():
    user_id = get_user_id()

    st.title("🌦️ 감정날씨 연구소")
    st.markdown(
        '<p class="subtitle">내 마음을 관찰하고 기록하는 작은 연구소</p>',
        unsafe_allow_html=True
    )

    with st.sidebar:
        st.markdown("## 🌷 메뉴")
        st.write(f"로그인 계정: **{st.session_state.username}**")

        page = st.radio(
            "이동할 메뉴",
            [
                "오늘의 감정 날씨",
                "나의 일기",
                "감정 달력",
                "감정 표현 연습",
                "감정 변화 분석",
                "월간 감정 보고서",
            ],
            key="main_menu",
            index=[
                "오늘의 감정 날씨",
                "나의 일기",
                "감정 달력",
                "감정 표현 연습",
                "감정 변화 분석",
                "월간 감정 보고서",
            ].index(st.session_state.get("page", "오늘의 감정 날씨"))
            if st.session_state.get("page", "오늘의 감정 날씨") in [
                "오늘의 감정 날씨",
                "나의 일기",
                "감정 달력",
                "감정 표현 연습",
                "감정 변화 분석",
                "월간 감정 보고서",
            ] else 0
        )

        st.session_state.page = page

        st.divider()

        if st.button("로그아웃", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    if page == "오늘의 감정 날씨":
        show_emotion_page(user_id)
    elif page == "나의 일기":
        show_diary_page(user_id)
    elif page == "감정 달력":
        show_calendar_page(user_id)
    elif page == "감정 표현 연습":
        show_expression_page()
    elif page == "감정 변화 분석":
        show_analysis_page(user_id)
    elif page == "월간 감정 보고서":
        show_monthly_report(user_id)


# ==========================================
# 13. 앱 실행
# ==========================================

if "user_id" not in st.session_state:
    show_login_page()
else:
    show_main_app()
