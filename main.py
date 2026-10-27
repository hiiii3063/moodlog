
import os
import sqlite3
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

[data-testid="stMetric"] {
    background-color: #FFFFFF;
    padding: 15px;
    border-radius: 12px;
    border: 1px solid #F0E2D3;
}

/* 일반 버튼 */
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

/* 지난 일기 목록은 사진처럼 간결한 글 형태로 표시 */
.st-key-past_diary_list div[data-testid="stButton"] button {
    background-color: transparent;
    border: none;
    box-shadow: none;
    color: #493F39;
    text-align: left;
    justify-content: flex-start;
    padding: 0.15rem 0;
    white-space: normal;
    height: auto;
}

.st-key-past_diary_list div[data-testid="stButton"] button:hover {
    background-color: #FCEBD8;
    border: none;
    color: #493F39;
}

.diary-content {
    background-color: #FFFFFF;
    border: 1px solid #EADBCB;
    border-radius: 12px;
    padding: 18px;
}
</style>
""", unsafe_allow_html=True)


# ==================================================
# 3. 데이터베이스
# ==================================================

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def get_columns(conn, table_name):
    return {
        row[1]
        for row in conn.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }


def ensure_column(conn, table_name, column_name, column_type):
    if column_name not in get_columns(conn, table_name):
        conn.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {column_type}"
        )


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
                weather TEXT NOT NULL DEFAULT '맑음',
                reason TEXT DEFAULT '',
                stress INTEGER DEFAULT 3,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS diaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                diary_date TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                photo_data BLOB,
                photo_mime TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 기존 데이터베이스의 누락된 열을 자동으로 추가
        emotion_columns = {
            "user_id": "INTEGER",
            "record_date": "TEXT",
            "weather": "TEXT DEFAULT '맑음'",
            "reason": "TEXT DEFAULT ''",
            "stress": "INTEGER DEFAULT 3",
            "created_at": "TEXT",
        }

        for name, column_type in emotion_columns.items():
            ensure_column(
                conn, "emotion_records", name, column_type
            )

        diary_columns = {
            "user_id": "INTEGER",
            "diary_date": "TEXT",
            "title": "TEXT DEFAULT ''",
            "content": "TEXT DEFAULT ''",
            "photo_data": "BLOB",
            "photo_mime": "TEXT",
            "updated_at": "TEXT",
        }

        for name, column_type in diary_columns.items():
            ensure_column(
                conn, "diaries", name, column_type
            )

        conn.execute("""
            UPDATE emotion_records
            SET weather = '맑음'
            WHERE weather IS NULL OR weather = ''
        """)

        conn.execute("""
            UPDATE emotion_records SET reason = ''
            WHERE reason IS NULL
        """)

        conn.execute("""
            UPDATE emotion_records SET stress = 3
            WHERE stress IS NULL
        """)

        conn.execute("""
            UPDATE diaries SET title = ''
            WHERE title IS NULL
        """)

        conn.execute("""
            UPDATE diaries SET content = ''
            WHERE content IS NULL
        """)

        conn.commit()


init_db()


# ==================================================
# 4. 데이터 조회 및 저장 함수
# ==================================================

def get_emotion_record(user_id, selected_date):
    with get_connection() as conn:
        return conn.execute("""
            SELECT weather, reason, stress
            FROM emotion_records
            WHERE user_id = ? AND record_date = ?
            ORDER BY id DESC LIMIT 1
        """, (user_id, selected_date)).fetchone()


def get_diary(user_id, selected_date):
    if not selected_date:
        return None

    with get_connection() as conn:
        return conn.execute("""
            SELECT id, diary_date, title, content, photo_data, photo_mime
            FROM diaries
            WHERE user_id = ? AND diary_date = ?
            ORDER BY id DESC LIMIT 1
        """, (user_id, selected_date)).fetchone()


def get_all_diaries(user_id):
    with get_connection() as conn:
        return conn.execute("""
            SELECT id, diary_date, title, content, photo_data, photo_mime
            FROM diaries
            WHERE user_id = ?
            ORDER BY diary_date DESC, id DESC
        """, (user_id,)).fetchall()


def save_emotion(user_id, record_date, weather, reason, stress):
    with get_connection() as conn:
        existing = conn.execute("""
            SELECT id FROM emotion_records
            WHERE user_id = ? AND record_date = ?
            ORDER BY id DESC LIMIT 1
        """, (user_id, record_date)).fetchone()

        if existing:
            conn.execute("""
                UPDATE emotion_records
                SET weather = ?, reason = ?, stress = ?
                WHERE id = ?
            """, (weather, reason, stress, existing[0]))
        else:
            conn.execute("""
                INSERT INTO emotion_records
                (user_id, record_date, weather, reason, stress)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, record_date, weather, reason, stress))

        conn.commit()


def save_diary(
    user_id, diary_date, title, content,
    photo_bytes=None, photo_mime=None
):
    existing = get_diary(user_id, diary_date)

    with get_connection() as conn:
        if existing:
            if photo_bytes is None:
                conn.execute("""
                    UPDATE diaries
                    SET title = ?, content = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (title, content, existing[0]))
            else:
                conn.execute("""
                    UPDATE diaries
                    SET title = ?, content = ?,
                        photo_data = ?, photo_mime = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    title, content, photo_bytes,
                    photo_mime, existing[0]
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


# ==================================================
# 5. 로그인 및 회원가입
# ==================================================

def show_login_page():
    st.title("감정날씨 연구소")
    st.write("오늘의 마음을 날씨처럼 기록해 보세요.")

    tab_login, tab_signup = st.tabs(["로그인", "회원가입"])

    with tab_login:
        username = st.text_input("아이디", key="login_username")
        password = st.text_input(
            "비밀번호", type="password", key="login_password"
        )

        if st.button("로그인", use_container_width=True):
            with get_connection() as conn:
                user = conn.execute("""
                    SELECT id, username, password_hash
                    FROM users WHERE username = ?
                """, (username.strip(),)).fetchone()

            if user and check_password_hash(user[2], password):
                st.session_state.user_id = user[0]
                st.session_state.username = user[1]
                st.session_state.page = "오늘의 감정 날씨"
                st.session_state.selected_diary_date = None
                st.session_state.calendar_selected_date = date.today().isoformat()
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호를 확인해 주세요.")

    with tab_signup:
        new_username = st.text_input(
            "사용할 아이디", key="signup_username"
        )
        new_password = st.text_input(
            "사용할 비밀번호", type="password", key="signup_password"
        )
        confirm_password = st.text_input(
            "비밀번호 확인", type="password", key="signup_confirm"
        )

        if st.button("회원가입", use_container_width=True):
            if not new_username.strip() or not new_password:
                st.warning("아이디와 비밀번호를 모두 입력해 주세요.")
            elif len(new_username.strip()) < 3:
                st.warning("아이디는 3글자 이상이어야 합니다.")
            elif len(new_password) < 4:
                st.warning("비밀번호는 4글자 이상이어야 합니다.")
            elif new_password != confirm_password:
                st.error("비밀번호가 서로 다릅니다.")
            else:
                try:
                    with get_connection() as conn:
                        conn.execute("""
                            INSERT INTO users (username, password_hash)
                            VALUES (?, ?)
                        """, (
                            new_username.strip(),
                            generate_password_hash(new_password)
                        ))
                        conn.commit()

                    st.success("회원가입이 완료되었습니다. 로그인해 주세요.")
                except sqlite3.IntegrityError:
                    st.error("이미 사용 중인 아이디입니다.")


# ==================================================
# 6. 오늘의 감정 날씨
# ==================================================

def show_emotion_page(user_id):
    st.header("오늘의 감정 날씨")
    st.write("오늘 내 마음은 어떤 날씨였나요?")

    selected_date = st.date_input(
        "기록할 날짜", value=date.today()
    )
    date_text = selected_date.isoformat()
    existing = get_emotion_record(user_id, date_text)

    weather_list = list(WEATHER_OPTIONS.keys())
    default_weather = existing[0] if existing else "맑음"
    default_reason = existing[1] if existing else ""
    default_stress = int(existing[2] or 3) if existing else 3

    weather = st.selectbox(
        "오늘의 감정 날씨",
        weather_list,
        index=weather_list.index(default_weather)
        if default_weather in weather_list else 0,
        format_func=lambda x: (
            f"{WEATHER_OPTIONS[x]['emoji']} {x}"
        )
    )

    reason = st.text_area(
        "그렇게 느낀 이유는 무엇인가요?",
        value=default_reason or "",
        placeholder="오늘 있었던 일이나 마음에 남은 순간을 적어 보세요."
    )

    stress = st.slider(
        "오늘의 스트레스 정도",
        min_value=1,
        max_value=5,
        value=default_stress
    )

    st.caption("1 매우 낮음 · 2 낮음 · 3 보통 · 4 높음 · 5 매우 높음")

    if st.button("감정 날씨 저장하기", use_container_width=True):
        save_emotion(user_id, date_text, weather, reason, stress)
        st.success("감정 날씨를 저장했습니다.")
        st.rerun()

    st.divider()
    st.subheader("오늘의 감정 처방")
    st.markdown(f"### {WEATHER_OPTIONS[weather]['emoji']} {weather}")
    st.write(EMOTION_ADVICE[weather])


# ==================================================
# 7. 일기 내용 표시
# ==================================================

def show_diary_content(diary):
    if not diary:
        st.info("이 날짜에 저장된 일기가 없습니다.")
        return

    st.markdown(f"### 📖 {diary[2] or '(제목 없음)'}")
    st.caption(f"작성 날짜: {diary[1]}")

    st.markdown(
        '<div class="diary-content">',
        unsafe_allow_html=True
    )
    st.write(diary[3] or "")
    st.markdown("</div>", unsafe_allow_html=True)

    if diary[4]:
        image_col, _ = st.columns([1, 2])
        with image_col:
            st.image(
                diary[4],
                width=DIARY_PHOTO_WIDTH,
                caption="첨부 사진"
            )


# ==================================================
# 8. 나의 일기
#    새 일기 작성 영역을 맨 위에 배치
# ==================================================

def show_diary_page(user_id):
    st.header("나의 일기")

    # --------------------------------------------------
    # 새 일기 쓰기 / 일기 수정하기: 페이지 맨 위
    # --------------------------------------------------

    edit_date = st.session_state.get("diary_edit_date")

    if edit_date:
        st.subheader("일기 수정하기")
        form_date = date.fromisoformat(edit_date)
    else:
        st.subheader("새 일기 쓰기")
        form_date = date.today()

    existing = get_diary(user_id, form_date.isoformat())

    with st.form("diary_form", clear_on_submit=False):
        diary_date = st.date_input(
            "일기 날짜",
            value=form_date,
            key=f"diary_date_input_{form_date.isoformat()}"
        )

        title = st.text_input(
            "일기 제목",
            value=existing[2] if existing else "",
            placeholder="예: 오늘 있었던 특별한 일",
            key=f"diary_title_input_{form_date.isoformat()}"
        )

        content = st.text_area(
            "일기 내용",
            value=existing[3] if existing else "",
            height=180,
            placeholder="오늘 있었던 일과 느낀 감정을 적어 보세요.",
            key=f"diary_content_input_{form_date.isoformat()}"
        )

        uploaded_photo = st.file_uploader(
            "사진 첨부하기 (선택)",
            type=["jpg", "jpeg", "png", "webp"],
            help="최대 5MB",
            key=f"diary_upload_{form_date.isoformat()}"
        )

        submitted = st.form_submit_button(
            "일기 저장하기",
            use_container_width=True
        )

    if existing and existing[4]:
        st.caption("현재 저장된 사진")

        image_col, _ = st.columns([1, 2])
        with image_col:
            st.image(existing[4], width=DIARY_PHOTO_WIDTH)

        if st.button(
            "현재 사진 삭제하기",
            key=f"remove_diary_photo_{form_date.isoformat()}"
        ):
            delete_diary_photo(user_id, form_date.isoformat())
            st.success("사진을 삭제했습니다.")
            st.rerun()

    photo_bytes = None
    photo_mime = None

    if uploaded_photo is not None:
        photo_bytes = uploaded_photo.getvalue()
        photo_mime = uploaded_photo.type

        if len(photo_bytes) > MAX_PHOTO_SIZE:
            st.error("사진 크기는 5MB 이하여야 합니다.")
        else:
            st.caption("업로드한 사진 미리 보기")

            image_col, _ = st.columns([1, 2])
            with image_col:
                st.image(photo_bytes, width=DIARY_PHOTO_WIDTH)

    if submitted:
        if not title.strip():
            st.warning("일기 제목을 입력해 주세요.")
        elif not content.strip():
            st.warning("일기 내용을 입력해 주세요.")
        elif (
            uploaded_photo is not None
            and len(uploaded_photo.getvalue()) > MAX_PHOTO_SIZE
        ):
            st.error("사진 크기는 5MB 이하여야 합니다.")
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
            st.success("일기를 저장했습니다.")
            st.rerun()

    if edit_date:
        if st.button("수정 취소", key="cancel_diary_edit"):
            st.session_state.diary_edit_date = None
            st.rerun()

    # --------------------------------------------------
    # 지난 일기: 작성 영역 아래에 사진과 같은 목록으로 표시
    # --------------------------------------------------

    st.divider()
    st.subheader("🗂️ 지난 일기")
    st.caption("날짜와 제목이 있는 줄을 누르면 일기를 읽을 수 있어요.")

    all_diaries = get_all_diaries(user_id)

    if not all_diaries:
        st.info("아직 작성한 일기가 없습니다.")
    else:
        # 컨테이너 안의 버튼만 목록처럼 보이도록 CSS 적용
        with st.container(key="past_diary_list"):
            for diary in all_diaries:
                diary_id = diary[0]
                diary_date = diary[1]
                diary_title = diary[2] or "(제목 없음)"
                photo_icon = " 📷" if diary[4] else ""

                # 날짜 또는 제목이 포함된 한 줄 전체를 클릭 가능하게 구성
                label = f"•　{diary_date} — {diary_title}{photo_icon}"

                if st.button(
                    label,
                    key=f"past_diary_{diary_id}",
                    use_container_width=True
                ):
                    st.session_state.selected_diary_date = diary_date
                    st.session_state.diary_edit_date = None
                    st.session_state.confirm_delete_diary = None
                    st.rerun()

    # --------------------------------------------------
    # 클릭한 일기 내용
    # --------------------------------------------------

    selected_date = st.session_state.get("selected_diary_date")
    selected = get_diary(user_id, selected_date) if selected_date else None

    if selected:
        st.divider()
        st.subheader("선택한 일기")
        show_diary_content(selected)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button(
                "닫기",
                key="close_selected_diary",
                use_container_width=True
            ):
                st.session_state.selected_diary_date = None
                st.rerun()

        with col2:
            if st.button(
                "수정하기",
                key="edit_selected_diary",
                use_container_width=True
            ):
                st.session_state.diary_edit_date = selected[1]
                st.rerun()

        with col3:
            if st.button(
                "삭제하기",
                key="delete_selected_diary",
                use_container_width=True
            ):
                st.session_state.confirm_delete_diary = selected[1]
                st.rerun()

    # 삭제 확인
    confirm_date = st.session_state.get("confirm_delete_diary")

    if confirm_date:
        st.warning(f"{confirm_date} 일기를 삭제할까요?")

        yes_col, no_col = st.columns(2)

        with yes_col:
            if st.button("삭제 확인", key="delete_diary_yes"):
                delete_diary(user_id, confirm_date)
                st.session_state.confirm_delete_diary = None
                st.success("일기를 삭제했습니다.")
                st.rerun()

        with no_col:
            if st.button("삭제 취소", key="delete_diary_no"):
                st.session_state.confirm_delete_diary = None
                st.rerun()


# ==================================================
# 9. 감정 달력
# ==================================================

def show_calendar_page(user_id):
    st.header("감정 달력")
    st.write("달력에서 날짜를 누르면 그날의 감정과 일기를 확인할 수 있어요.")

    today = date.today()

    year_col, month_col = st.columns(2)

    with year_col:
        years = list(range(today.year - 5, today.year + 1))
        year = st.selectbox(
            "연도",
            years,
            index=len(years) - 1,
            key="calendar_year"
        )

    with month_col:
        month = st.selectbox(
            "월",
            list(range(1, 13)),
            index=today.month - 1,
            key="calendar_month"
        )

    month_text = f"{year:04d}-{month:02d}"

    with get_connection() as conn:
        emotion_rows = conn.execute("""
            SELECT record_date, weather, reason, stress
            FROM emotion_records
            WHERE user_id = ? AND substr(record_date, 1, 7) = ?
            ORDER BY id
        """, (user_id, month_text)).fetchall()

        diary_rows = conn.execute("""
            SELECT id, diary_date, title, content, photo_data, photo_mime
            FROM diaries
            WHERE user_id = ? AND substr(diary_date, 1, 7) = ?
            ORDER BY id DESC
        """, (user_id, month_text)).fetchall()

    emotions = {
        row[0]: {
            "weather": row[1],
            "reason": row[2] or "",
            "stress": row[3]
        }
        for row in emotion_rows
    }

    diaries = {}
    for row in diary_rows:
        if row[1] not in diaries:
            diaries[row[1]] = row

    weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(
        year, month
    )

    # 요일 표시
    header_cols = st.columns(7)

    for col, day_name in zip(
        header_cols, ["일", "월", "화", "수", "목", "금", "토"]
    ):
        with col:
            st.markdown(f"**{day_name}**")

    # 날짜 버튼
    for week_index, week in enumerate(weeks):
        cols = st.columns(7)

        for col_index, day_num in enumerate(week):
            with cols[col_index]:
                if day_num == 0:
                    st.write(" ")
                    continue

                day_text = date(year, month, day_num).isoformat()
                emotion = emotions.get(day_text)
                diary = diaries.get(day_text)

                label = str(day_num)

                if emotion:
                    emoji = WEATHER_OPTIONS.get(
                        emotion["weather"], {"emoji": "🌦️"}
                    )["emoji"]
                    label += f"\n{emoji}"

                if diary:
                    label += "\n📔"

                if st.button(
                    label,
                    key=f"calendar_day_{year}_{month}_{day_num}",
                    use_container_width=True
                ):
                    st.session_state.calendar_selected_date = day_text
                    st.rerun()

    st.caption(
        "감정 날씨 아이콘은 감정 기록, 📔는 일기가 있다는 뜻입니다."
    )

    # 선택 날짜 상세 내용
    selected_date = st.session_state.get("calendar_selected_date")

    if selected_date:
        selected_obj = date.fromisoformat(selected_date)

        if selected_obj.year != year or selected_obj.month != month:
            selected_date = None

    if selected_date:
        st.divider()
        st.subheader(f"{selected_date} 기록")

        emotion = emotions.get(selected_date)
        diary = diaries.get(selected_date)

        if emotion:
            weather = emotion["weather"]
            emoji = WEATHER_OPTIONS.get(
                weather, {"emoji": "🌦️"}
            )["emoji"]

            st.markdown(f"### {emoji} 감정 날씨: {weather}")

            if emotion["reason"]:
                st.write(f"**감정을 느낀 이유:** {emotion['reason']}")

            if emotion["stress"] is not None:
                st.write(
                    f"**스트레스 정도:** {emotion['stress']} / 5"
                )
        else:
            st.info("이 날짜에는 감정 날씨 기록이 없습니다.")

        st.divider()
        st.markdown("### 일기")

        if diary:
            show_diary_content(diary)

            if st.button(
                "일기 수정하기",
                key=f"calendar_edit_{selected_date}"
            ):
                st.session_state.page = "나의 일기"
                st.session_state.diary_edit_date = selected_date
                st.session_state.selected_diary_date = selected_date
                st.rerun()
        else:
            st.info("이 날짜에는 저장된 일기가 없습니다.")

        if st.button(
            "선택한 날짜 닫기",
            key="close_calendar_detail"
        ):
            st.session_state.calendar_selected_date = None
            st.rerun()


# ==================================================
# 10. 감정 표현 연습
# ==================================================

def show_expression_page():
    st.header("감정 표현 연습")
    st.write("내 감정을 구체적인 말로 표현해 보세요.")

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
        ]
    }

    situation = st.selectbox(
        "상황 선택하기", list(situations.keys())
    )

    st.subheader("표현 예시")

    for sentence in situations[situation]:
        st.info(sentence)

    expression = st.text_area(
        "나만의 문장 만들기",
        placeholder="나는 ______해서 ______한 기분이 들었어."
    )

    if expression.strip():
        st.success("감정을 문장으로 표현해 보았어요.")


# ==================================================
# 11. 감정 변화 분석
# ==================================================

def show_analysis_page(user_id):
    st.header("감정 변화 분석")
    st.write("감정 점수와 스트레스의 변화를 비교해 보세요.")

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT record_date, weather, stress, reason
            FROM emotion_records
            WHERE user_id = ?
            ORDER BY record_date, id
        """, (user_id,)).fetchall()

    if not rows:
        st.info("분석할 기록이 없습니다. 감정 날씨를 먼저 기록해 보세요.")
        return

    df = pd.DataFrame(
        rows, columns=["날짜", "감정 날씨", "스트레스", "이유"]
    )

    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df = df.dropna(subset=["날짜"])

    df["감정 점수"] = df["감정 날씨"].map(
        lambda x: WEATHER_OPTIONS.get(x, {"score": 3})["score"]
    )

    df["스트레스"] = pd.to_numeric(
        df["스트레스"], errors="coerce"
    ).fillna(3)

    if df.empty:
        st.info("날짜가 올바른 기록이 없습니다.")
        return

    min_date = df["날짜"].min().date()
    max_date = df["날짜"].max().date()

    if min_date == max_date:
        start_date, end_date = min_date, max_date
    else:
        date_range = st.date_input(
            "분석 기간",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

        if not isinstance(date_range, (tuple, list)) or len(date_range) != 2:
            st.info("시작일과 종료일을 모두 선택해 주세요.")
            return

        start_date, end_date = date_range

    filtered = df[
        (df["날짜"].dt.date >= start_date)
        & (df["날짜"].dt.date <= end_date)
    ].copy()

    if filtered.empty:
        st.info("선택한 기간에 기록이 없습니다.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("기록한 날", f"{filtered['날짜'].nunique()}일")
    c2.metric(
        "평균 감정 점수",
        f"{filtered['감정 점수'].mean():.1f} / 5"
    )
    c3.metric(
        "평균 스트레스",
        f"{filtered['스트레스'].mean():.1f} / 5"
    )

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=filtered["날짜"],
        y=filtered["감정 점수"],
        mode="lines+markers",
        name="감정 점수"
    ))

    fig.add_trace(go.Scatter(
        x=filtered["날짜"],
        y=filtered["스트레스"],
        mode="lines+markers",
        name="스트레스",
        line=dict(dash="dash")
    ))

    fig.update_layout(
        title="감정과 스트레스 변화",
        xaxis_title="날짜",
        yaxis_title="점수 (1~5)",
        yaxis=dict(range=[0, 5.5], dtick=1),
        hovermode="x unified",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFF9F0"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("기록 목록")

    st.dataframe(
        filtered[
            ["날짜", "감정 날씨", "감정 점수", "스트레스", "이유"]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "감정 점수는 참고용이며 심리 상태를 진단하는 지표가 아닙니다."
    )


# ==================================================
# 12. 월간 감정 보고서
# ==================================================

def show_monthly_report(user_id):
    st.header("월간 감정 연구 보고서")

    today = date.today()

    year_col, month_col = st.columns(2)

    with year_col:
        years = list(range(today.year - 5, today.year + 1))
        year = st.selectbox(
            "연도",
            years,
            index=len(years) - 1,
            key="report_year"
        )

    with month_col:
        month = st.selectbox(
            "월",
            list(range(1, 13)),
            index=today.month - 1,
            key="report_month"
        )

    month_text = f"{year:04d}-{month:02d}"

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT record_date, weather, reason, stress
            FROM emotion_records
            WHERE user_id = ? AND substr(record_date, 1, 7) = ?
            ORDER BY record_date
        """, (user_id, month_text)).fetchall()

        diary_count = conn.execute("""
            SELECT COUNT(*) FROM diaries
            WHERE user_id = ? AND substr(diary_date, 1, 7) = ?
        """, (user_id, month_text)).fetchone()[0]

    df = pd.DataFrame(
        rows, columns=["날짜", "감정 날씨", "이유", "스트레스"]
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("감정 기록", f"{len(df)}일")
    c2.metric("작성한 일기", f"{diary_count}개")

    if df.empty:
        c3.metric("평균 스트레스", "-")
        st.info("해당 월에 감정 기록이 없습니다.")
        return

    df["스트레스"] = pd.to_numeric(
        df["스트레스"], errors="coerce"
    ).fillna(3)

    c3.metric(
        "평균 스트레스",
        f"{df['스트레스'].mean():.1f} / 5"
    )

    counts = df["감정 날씨"].value_counts()
    most_common = counts.index[0]

    st.subheader("가장 자주 기록한 감정 날씨")
    st.write(
        f"{WEATHER_OPTIONS.get(most_common, {'emoji': '🌦️'})['emoji']} "
        f"**{most_common}** ({int(counts.iloc[0])}회)"
    )

    fig = go.Figure(go.Bar(
        x=counts.index,
        y=counts.values,
        text=counts.values,
        textposition="auto"
    ))

    fig.update_layout(
        title="감정 날씨별 기록 횟수",
        xaxis_title="감정 날씨",
        yaxis_title="기록 횟수",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFF9F0"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("이번 달 기록")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.subheader("스스로 돌아볼 질문")
    st.write("- 이번 달에 가장 자주 느낀 감정은 무엇이었나요?")
    st.write("- 기분이 좋아졌던 날에는 어떤 일이 있었나요?")
    st.write("- 스트레스가 높았던 날 나에게 도움이 된 것은 무엇인가요?")
    st.write("- 다음 달에는 어떤 감정 표현을 연습하고 싶나요?")


# ==================================================
# 13. 메인 앱
# ==================================================

def show_main_app():
    user_id = st.session_state.user_id

    st.title("감정날씨 연구소")
    st.markdown(
        '<p class="subtitle">내 마음을 관찰하고 기록하는 작은 연구소</p>',
        unsafe_allow_html=True
    )

    pages = [
        "오늘의 감정 날씨",
        "나의 일기",
        "감정 달력",
        "감정 표현 연습",
        "감정 변화 분석",
        "월간 감정 보고서"
    ]

    with st.sidebar:
        st.markdown("## 🌷 메뉴")
        st.write(f"로그인 계정: **{st.session_state.username}**")

        current_page = st.session_state.get(
            "page", "오늘의 감정 날씨"
        )

        if current_page not in pages:
            current_page = pages[0]

        page = st.radio(
            "이동할 메뉴",
            pages,
            index=pages.index(current_page)
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


# ==================================================
# 14. 앱 실행
# ==================================================

if "user_id" not in st.session_state:
    show_login_page()
else:
    show_main_app()
