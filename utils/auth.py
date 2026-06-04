import hashlib

import streamlit as st


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_default_password(password: str) -> bool:
    """Validates against the shared default password used for first login."""
    return _hash(password) == st.secrets["auth"]["password_hash"]


def check_personal_password(username: str, password: str) -> bool:
    """Validates against the user's own password stored in Supabase."""
    from utils.db import get_user
    user = get_user(username)
    if not user or not user.get("password_hash"):
        return False
    return _hash(password) == user["password_hash"]


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
