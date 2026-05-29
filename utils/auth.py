import hashlib

import streamlit as st
import yaml

_CONFIG_PATH = "config.yaml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def check_login(username: str, password: str) -> bool:
    config = _load_config()
    users = {u["username"]: u for u in config["users"]}
    if username not in users:
        return False
    return _hash(password) == config["password_hash"]


def get_firstname(username: str) -> str:
    config = _load_config()
    for user in config["users"]:
        if user["username"] == username:
            return user["firstname"]
    return username


def get_user_map() -> dict[str, str]:
    """Returns {username: firstname} for all users in config.yaml."""
    config = _load_config()
    return {u["username"]: u["firstname"] for u in config["users"]}


def require_login() -> str:
    """Stops execution if not authenticated. Returns the logged-in username."""
    if not st.session_state.get("authenticated"):
        st.stop()

    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()

    return st.session_state["username"]
