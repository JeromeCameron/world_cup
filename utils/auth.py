import hashlib

import streamlit as st


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_login(username: str, password: str) -> bool:
    from utils.db import get_user_map
    if _hash(password) != st.secrets["auth"]["password_hash"]:
        return False
    return username in get_user_map()


def get_firstname(username: str) -> str:
    from utils.db import get_firstname as _get
    return _get(username)


def get_user_map() -> dict[str, str]:
    from utils.db import get_user_map as _get
    return _get()


def require_login() -> str:
    if not st.session_state.get("authenticated"):
        st.stop()
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    return st.session_state["username"]
