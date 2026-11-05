        change_submitted = st.form_submit_button(
            "비밀번호 변경", use_container_width=True
        )

    if change_submitted:
        result = supabase.table("account").select("password_hash").eq("id", user_id).limit(1).execute()
        rows = result.data or []
        row = rows[0] if rows else None

        if not row or not check_password_hash(row["password_hash"], current_password):
            st.error("현재 비밀번호가 올바르지 않습니다.")
        elif len(new_password) < 8:
            st.warning("새 비밀번호는 8자 이상으로 설정해 주세요.")
        elif new_password != confirm_new_password:
            st.error("새 비밀번호가 서로 일치하지 않습니다.")
        elif check_password_hash(row["password_hash"], new_password):
            st.warning("현재 비밀번호와 다른 비밀번호를 입력해 주세요.")
        else:
            supabase.table("account").update({
                "password_hash": generate_password_hash(new_password)
            }).eq("id", user_id).execute()
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
            result = supabase.table("account").select("password_hash").eq("id", user_id).limit(1).execute()
            rows = result.data or []
            row = rows[0] if rows else None

            if not row or not check_password_hash(row["password_hash"], delete_password):
                st.error("비밀번호가 올바르지 않습니다. 계정을 삭제하지 않았습니다.")
            else:
                supabase.table("diary").delete().eq("user_id", user_id).execute()
                supabase.table("emotion").delete().eq("user_id", user_id).execute()
                supabase.table("account").delete().eq("id", user_id).execute()
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
