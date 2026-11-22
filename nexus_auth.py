"""Nexus Fitness — вход и регистрация: Google (Streamlit Auth) или свой e-mail."""

import hashlib
import os
import re
import secrets
import sqlite3

import streamlit as st

DB_PATH = "users.db"

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+$")


def _db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
               email TEXT PRIMARY KEY,
               name TEXT,
               salt TEXT,
               password_hash TEXT
           )"""
    )
    return conn


def _hash_password(password: str, salt: str) -> str:
    """PBKDF2-SHA256, 200 000 итераций. Пароль в открытом виде нигде не хранится."""
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000
    ).hex()


def register(email: str, name: str, password: str):
    """Создаёт пользователя. Возвращает None при успехе или текст ошибки."""
    email = email.strip().lower()
    if not _EMAIL_RE.match(email):
        return "Похоже, это не email — проверь адрес."
    if len(password) < 6:
        return "Пароль слишком короткий — минимум 6 символов."
    conn = _db()
    if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        conn.close()
        return "Пользователь с такой почтой уже зарегистрирован."
    salt = secrets.token_hex(16)
    conn.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?)",
        (email, name.strip() or email.split("@")[0], salt, _hash_password(password, salt)),
    )
    conn.commit()
    conn.close()
    return None


def login(email: str, password: str) -> bool:
    email = email.strip().lower()
    conn = _db()
    row = conn.execute(
        "SELECT salt, password_hash FROM users WHERE email=?", (email,)
    ).fetchone()
    conn.close()
    if not row:
        return False
    salt, stored = row
    return secrets.compare_digest(_hash_password(password, salt), stored)


def google_available() -> bool:
    """Google-вход включён, если в secrets.toml заполнен [auth.google]."""
    try:
        import authlib  # noqa: F401
    except ImportError:
        return False
    try:
        g = st.secrets["auth"]["google"]
        return bool(g.get("client_id") and g.get("client_secret"))
    except Exception:
        return False


def current_user():
    """Текущий пользователь: сначала Google, затем свой e-mail из сессии."""
    # 1) Google через Streamlit Auth
    try:
        if st.user.is_logged_in:
            email = str(st.user.email or "").lower()
            if email:
                return {"email": email, "name": st.user.name or email}
    except Exception:
        pass
    # 2) свой e-mail
    if st.session_state.get("auth_user"):
        return st.session_state["auth_user"]
    return None


def logout_button():
    if st.button("🚪 Выйти", use_container_width=True):
        try:
            st.logout()
        except Exception:
            pass
        st.session_state["auth_user"] = None
        st.rerun()


def _show_header():
    """Шапка экрана входа: логотип, если он есть, иначе эмодзи-запаска."""
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_logo.png")
    if os.path.exists(logo_path):
        col_logo, col_title = st.columns([1, 4])
        with col_logo:
            st.image(logo_path, width=72)
        with col_title:
            st.markdown("## Nexus Fitness")
    else:
        st.markdown("## 💪 Nexus Fitness")


def auth_screen():
    """Экран входа/регистрации. Показывается, когда пользователь не залогинен."""
    _show_header()
    st.caption("Войдите, чтобы сохранить свой профиль, план и прогресс")

    tab_login, tab_reg = st.tabs(["Вход", "Регистрация"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Пароль", type="password")
            ok = st.form_submit_button("Войти", use_container_width=True)
        if ok:
            if login(email, password):
                conn = _db()
                row = conn.execute(
                    "SELECT name FROM users WHERE email=?", (email.strip().lower(),)
                ).fetchone()
                conn.close()
                st.session_state["auth_user"] = {
                    "email": email.strip().lower(),
                    "name": row[0] if row else "Атлет",
                }
                st.rerun()
            else:
                st.error("Неверный email или пароль.")

    with tab_reg:
        with st.form("reg_form"):
            r_email = st.text_input("Email", key="reg_email")
            r_name = st.text_input("Имя", key="reg_name", placeholder="Как к вам обращаться")
            r_pass = st.text_input("Пароль (минимум 6 символов)", type="password", key="reg_pass")
            ok = st.form_submit_button("Создать аккаунт", use_container_width=True)
        if ok:
            err = register(r_email, r_name, r_pass)
            if err:
                st.error(err)
            else:
                st.session_state["auth_user"] = {
                    "email": r_email.strip().lower(),
                    "name": r_name.strip() or r_email.split("@")[0],
                }
                st.rerun()

    if google_available():
        st.divider()
        st.caption("Или войдите через Google:")
        if st.button("🔵 Продолжить с Google", use_container_width=True):
            st.login("google")
