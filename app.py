import streamlit as st

from utils.auth import (
    _hash,
    check_default_password,
    check_personal_password,
    get_firstname,
)
from utils.db import get_user, set_user_password, update_last_login

st.set_page_config(
    page_title="World Cup 2026",
    page_icon="⚽",
    layout="centered",
    initial_sidebar_state="expanded",
)

LOGIN_CSS = """
<style>
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    .login-header { text-align: center; padding: 2rem 0 1rem 0; }
    .login-header h1 { font-size: 2.8rem; margin-bottom: 0.2rem; }
    .login-header p  { font-size: 1.1rem; color: #888; margin-top: 0; }
    div[data-testid="stForm"] {
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 2rem;
        background: white;
    }
</style>
"""

# -------  Login page  ---------------------------------------------------------
if not st.session_state.get("authenticated"):
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown(
            '<div class="login-header"><h1>⚽ World Cup 2026</h1><p>Predict & Win</p></div>',
            unsafe_allow_html=True,
        )

        # ── Step 2: set personal password after verifying default ──────────
        if st.session_state.get("pending_password_setup"):
            pending_user = st.session_state["pending_username"]
            st.info(f"Welcome! Please create your personal password, **{get_firstname(pending_user)}**.")
            with st.form("set_password_form"):
                new_pass = st.text_input("New password", type="password")
                confirm_pass = st.text_input("Confirm password", type="password")
                set_submitted = st.form_submit_button("Set Password", use_container_width=True)
            if set_submitted:
                if len(new_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                elif new_pass != confirm_pass:
                    st.error("Passwords do not match.")
                else:
                    set_user_password(pending_user, _hash(new_pass))
                    st.session_state.pop("pending_password_setup")
                    st.session_state.pop("pending_username")
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = pending_user
                    st.session_state["firstname"] = get_firstname(pending_user)
                    st.rerun()

        # ── Step 1: login form ─────────────────────────────────────────────
        else:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                uname = username.strip()
                user = get_user(uname)
                if not user:
                    st.error("Incorrect username or password.")
                elif user.get("last_login") is None:
                    # First login — verify default password then prompt for personal one
                    if check_default_password(password):
                        st.session_state["pending_password_setup"] = True
                        st.session_state["pending_username"] = uname
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")
                else:
                    # Returning user — verify personal password
                    if check_personal_password(uname, password):
                        update_last_login(uname)
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = uname
                        st.session_state["firstname"] = get_firstname(uname)
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")

    st.stop()

# -------  Navigation  ---------------------------------------------------------
pages = [
    st.Page("pages/home.py", title="🏠 Home"),
    st.Page("pages/predictions.py", title="🤔 Predictions"),
    st.Page("pages/leaderboard.py", title="🏆 Leaderboard"),
    st.Page("pages/view_predictions.py", title="👀 View Predictions"),
]

if st.session_state.get("username") == "jimmy":
    pages.append(st.Page("pages/admin.py", title="🎮 Admin"))

pg = st.navigation(pages)
pg.run()
