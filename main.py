
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
.stButton > button,
.stFormSubmitButton > button {
    background-color: #E6EED8;
    color: #4F6242;
    border: 1px solid #D5E2C5;
    border-radius: 14px;
    padding: 0.45rem 1rem;
    transition: background-color 0.2s ease;
}

/* 버튼에 마우스를 올렸을 때 */
.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background-color: #D6E5C1;
    border-color: #C3D5AC;
    color: #405437;
}

/* 입력 칸 선택 시 */
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: #A9C58D;
    box-shadow: 0 0 0 1px #A9C58D;
}

/* 지표 카드 */
[data-testid="stMetric"] {
    background-color: #FFFEF8;
    padding: 16px;
    border-radius: 16px;
    border: 1px solid #E3E9D7;
}

/* 탭 */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background-color: #F3F4E8;
    border-radius: 14px;
    padding: 5px;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
}

/* 알림 상자 */
.stAlert {
    border-radius: 14px;
}

/* 구분선 */
hr {
    border-color: #E5E8D9;
}

/* 지난 일기 목록: 기존의 간결한 글머리표 디자인 유지 */
.st-key-past_diary_list div[data-testid="stButton"] button {
    background-color: transparent;
    border: none;
    box-shadow: none;
    color: #4F5847;
    text-align: left;
    justify-content: flex-start;
    padding: 0.15rem 0;
    white-space: normal;
    height: auto;
}

.st-key-past_diary_list div[data-testid="stButton"] button:hover {
    background-color: #EDF2E3;
    border: none;
    color: #405437;
}

/* 일기 내용 */
.diary-content {
    background-color: #FFFEF8;
    border: 1px solid #E1E8D3;
    border-radius: 16px;
    padding: 20px;
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
            elif len(new_password) < 8:
                st.warning("비밀번호는 8글자 이상이어야 합니다.")
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

    # 테두리와 흰색 배경을 하나의 박스로 만들어 가장자리가 어긋나지 않게 표시
    diary_text = (diary[3] or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace(chr(10), '<br>')
    st.markdown(
        f"<div style='box-sizing:border-box; width:100%; margin:0; "
        f"border:1px solid #D8D1C2; border-radius:10px; "
        f"background-color:#FFFEF8; padding:16px; "
        f"white-space:pre-wrap; overflow-wrap:anywhere; color:#4F5847;'>"
        f"{diary_text}"
        f"</div>",
        unsafe_allow_html=True
    )

    if diary[4]:
        image_col, _ = st.columns([1, 2])
        with image_col:
            st.image(
                diary[4],
                width=DIARY_PHOTO_WIDTH,
                caption="첨부 사진"
            )


def clear_diary_fields_after_saved_date_change():
    """저장한 뒤 날짜를 바꾸면 작성 입력란을 비운다."""
    saved_date = st.session_state.get("diary_saved_date")
    new_date = st.session_state.get("diary_date_picker")

    if saved_date and new_date and str(new_date) != str(saved_date):
        st.session_state.pop("diary_title", None)
        st.session_state.pop("diary_content", None)
        st.session_state.pop("diary_upload", None)
        st.session_state.diary_saved_date = None


def show_diary_page(user_id):
    st.header("나의 일기")

    # 새 일기 쓰기 영역을 맨 위에 배치
    edit_date = st.session_state.get("diary_edit_date")

    if edit_date:
        st.subheader("일기 수정하기")
        default_date = date.fromisoformat(edit_date)
    else:
        st.subheader("새 일기 쓰기")
        default_date = date.today()

    if "diary_date_picker" not in st.session_state:
        st.session_state.diary_date_picker = default_date

    # 날짜 선택은 폼 바깥에 두어 날짜 변경 즉시 반영
    diary_date = st.date_input(
        "일기 날짜",
        value=st.session_state.diary_date_picker,
        key="diary_date_picker",
        on_change=clear_diary_fields_after_saved_date_change
    )

    date_text = diary_date.isoformat()
    existing = get_diary(user_id, date_text) if edit_date else None

    # 수정 모드에 처음 진입했을 때만 기존 내용을 입력란에 채운다.
    if edit_date and not st.session_state.get("diary_edit_fields_loaded"):
        if existing:
            st.session_state.diary_title = existing[2] or ""
            st.session_state.diary_content = existing[3] or ""
        st.session_state.diary_edit_fields_loaded = True

    with st.form("diary_form", clear_on_submit=False):
        title = st.text_input(
            "일기 제목",
            value=existing[2] if existing and "diary_title" not in st.session_state else "",
            placeholder="예: 오늘 있었던 특별한 일",
            key="diary_title"
        )

        content = st.text_area(
            "일기 내용",
            value=existing[3] if existing and "diary_content" not in st.session_state else "",
            height=180,
            placeholder="오늘 있었던 일과 느낀 감정을 적어 보세요.",
            key="diary_content"
        )

        uploaded_photo = st.file_uploader(
            "사진 첨부하기 (선택)",
            type=["jpg", "jpeg", "png", "webp"],
            help="최대 5MB",
            key="diary_upload"
        )

        submitted = st.form_submit_button(
            "일기 저장하기",
            use_container_width=True
        )

    # 기존에 저장된 사진만 표시하며, 새로 업로드한 사진 미리보기는 표시하지 않는다.
    if existing and existing[4]:
        st.caption("현재 저장된 사진")
        image_col, _ = st.columns([1, 2])
        with image_col:
            st.image(existing[4], width=DIARY_PHOTO_WIDTH)

        if st.button("현재 사진 삭제하기", key=f"remove_diary_photo_{date_text}"):
            delete_diary_photo(user_id, date_text)
            st.success("사진을 삭제했습니다.")
            st.rerun()

    photo_bytes = uploaded_photo.getvalue() if uploaded_photo is not None else None
    photo_mime = uploaded_photo.type if uploaded_photo is not None else None

    if submitted:
        if not title.strip():
            st.warning("일기 제목을 입력해 주세요.")
        elif not content.strip():
            st.warning("일기 내용을 입력해 주세요.")
        elif photo_bytes is not None and len(photo_bytes) > MAX_PHOTO_SIZE:
            st.error("사진 크기는 5MB 이하여야 합니다.")
        else:
            save_diary(
                user_id,
                date_text,
                title.strip(),
                content.strip(),
                photo_bytes,
                photo_mime
            )
            st.session_state.selected_diary_date = date_text
            st.session_state.diary_saved_date = date_text
            st.session_state.diary_edit_date = None
            st.session_state.diary_edit_fields_loaded = False
            st.success("일기를 저장했습니다.")
            st.rerun()

    if edit_date:
        if st.button("수정 취소", key="cancel_diary_edit"):
            st.session_state.diary_edit_date = None
            st.session_state.diary_edit_fields_loaded = False
            st.rerun()

    # 지난 일기 목록
    st.divider()
    st.subheader("🗂️ 지난 일기")
    st.caption("날짜와 제목이 있는 줄을 누르면 일기를 읽을 수 있어요.")

    all_diaries = get_all_diaries(user_id)

    if not all_diaries:
        st.info("아직 작성한 일기가 없습니다.")
    else:
        with st.container(key="past_diary_list"):
            for diary in all_diaries:
                diary_id = diary[0]
                diary_date = diary[1]
                diary_title = diary[2] or "(제목 없음)"
                photo_icon = " 📷" if diary[4] else ""
                label = f"•　{diary_date} — {diary_title}{photo_icon}"

                if st.button(
                    label,
                    key=f"past_diary_{diary_id}",
                    use_container_width=True
                ):
                    st.session_state.selected_diary_date = diary_date
                    st.session_state.diary_edit_date = None
                    st.session_state.diary_edit_fields_loaded = False
                    st.session_state.confirm_delete_diary = None
                    st.rerun()

    selected_date = st.session_state.get("selected_diary_date")
    selected = get_diary(user_id, selected_date) if selected_date else None

    if selected:
        st.divider()
        st.subheader("선택한 일기")
        show_diary_content(selected)

        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("닫기", key="close_selected_diary", use_container_width=True):
                st.session_state.selected_diary_date = None
                st.rerun()

        with col2:
            if st.button("수정하기", key="edit_selected_diary", use_container_width=True):
                st.session_state.diary_edit_date = selected[1]
                st.session_state.diary_date_picker = date.fromisoformat(selected[1])
                st.session_state.diary_edit_fields_loaded = False
                st.session_state.pop("diary_title", None)
                st.session_state.pop("diary_content", None)
                st.session_state.pop("diary_upload", None)
                st.rerun()

        with col3:
            if st.button("삭제하기", key="delete_selected_diary", use_container_width=True):
                st.session_state.confirm_delete_diary = selected[1]
                st.rerun()

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
    st.header("💬 감정 표현 연습실")
    st.write("상황, 감정, 필요한 것을 연결해 문장을 만들어 봐요.")

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
# 내 정보: 비밀번호 변경 및 계정 삭제
# ==================================================

def show_my_info_page(user_id):
    st.header("내 정보")
    st.write(f"로그인 아이디: **{st.session_state.username}**")

    st.subheader("비밀번호 변경")
    with st.form("change_password_form"):
        current_password = st.text_input(
            "현재 비밀번호", type="password", key="myinfo_current_password"
        )
        new_password = st.text_input(
            "새 비밀번호", type="password", key="myinfo_new_password"
        )
        confirm_new_password = st.text_input(
            "새 비밀번호 확인", type="password", key="myinfo_confirm_password"
        )
        change_submitted = st.form_submit_button(
            "비밀번호 변경", use_container_width=True
        )

    if change_submitted:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT password_hash FROM users WHERE id = ?",
                (user_id,)
            ).fetchone()

            if not row or not check_password_hash(row[0], current_password):
                st.error("현재 비밀번호가 올바르지 않습니다.")
            elif len(new_password) < 8:
                st.warning("새 비밀번호는 8자 이상으로 설정해 주세요.")
            elif new_password != confirm_new_password:
                st.error("새 비밀번호가 서로 일치하지 않습니다.")
            elif check_password_hash(row[0], new_password):
                st.warning("현재 비밀번호와 다른 비밀번호를 입력해 주세요.")
            else:
                conn.execute(
                    "UPDATE users SET password_hash = ? WHERE id = ?",
                    (generate_password_hash(new_password), user_id)
                )
                conn.commit()
                st.success("비밀번호가 변경되었습니다.")

    st.divider()
    st.subheader("계정 삭제")
    st.warning("계정을 삭제하면 이 계정의 감정 기록과 일기가 모두 삭제되며 되돌릴 수 없습니다.")

    with st.form("delete_account_form"):
        delete_password = st.text_input(
            "계정 삭제를 위해 현재 비밀번호를 입력하세요",
            type="password",
            key="myinfo_delete_password"
        )
        confirm_delete = st.checkbox(
            "감정 기록과 일기를 포함한 계정 데이터가 모두 삭제되는 것에 동의합니다.",
            key="myinfo_confirm_delete"
        )
        delete_submitted = st.form_submit_button(
            "계정 삭제", use_container_width=True
        )

    if delete_submitted:
        if not confirm_delete:
            st.error("계정 삭제 동의 항목을 확인해 주세요.")
        else:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT password_hash FROM users WHERE id = ?",
                    (user_id,)
                ).fetchone()

                if not row or not check_password_hash(row[0], delete_password):
                    st.error("비밀번호가 올바르지 않습니다. 계정을 삭제하지 않았습니다.")
                else:
                    conn.execute("DELETE FROM diaries WHERE user_id = ?", (user_id,))
                    conn.execute("DELETE FROM emotion_records WHERE user_id = ?", (user_id,))
                    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    conn.commit()
                    st.session_state.clear()
                    st.rerun()


# ==================================================
# 13. 메인 앱
# ==================================================

def show_main_app():
    user_id = st.session_state.user_id

    st.title("감정날씨 연구소")

    pages = [
        "오늘의 감정 날씨",
        "나의 일기",
        "감정 달력",
        "감정 표현 연습",
        "감정 변화 분석",
        "월간 감정 보고서",
        "내 정보"
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
    elif page == "내 정보":
        show_my_info_page(user_id)


# ==================================================
# 14. 앱 실행
# ==================================================

if "user_id" not in st.session_state:
    show_login_page()
else:
    show_main_app()
