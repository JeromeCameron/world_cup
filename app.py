import streamlit as st

from utils.auth import check_login, get_firstname

# -------  Login page  ---------------------------------------------------------
if not st.session_state.get("authenticated"):
    st.markdown(
        """
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
        .login-header {
            text-align: center;
            padding: 2rem 0 1rem 0;
        }
        .login-header h1 { font-size: 2.8rem; margin-bottom: 0.2rem; }
        .login-header p  { font-size: 1.1rem; color: #888; margin-top: 0; }
        div[data-testid="stForm"] {
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 2rem;
            background: white;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown(
            """
        <div class="login-header">
            <h1>⚽ World Cup 2026</h1>
            <p>Predict & Win</p>
        </div>
        """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

        if submitted:
            if check_login(username.strip(), password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username.strip()
                st.session_state["firstname"] = get_firstname(username.strip())
                st.rerun()
            else:
                st.error("Incorrect username or password")

    st.stop()

# -------  Navigation  ---------------------------------------------------------
pages = [
    st.Page("pages/home.py", title="🏠 Home"),
    st.Page("pages/predictions.py", title="🤔 Predictions"),
    st.Page("pages/leaderboard.py", title="🏆 Leaderboard"),
    st.Page("pages/view_predictions.py", title="👀 View Predictions"),
]

if st.session_state.get("username") == "data":
    pages.append(st.Page("pages/admin.py", title="🎮 Admin"))

pg = st.navigation(pages)
pg.run()
