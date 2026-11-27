"""Nexus Fitness — интерфейс на Streamlit. Запуск: streamlit run app.py"""

import os
import re
import time
from datetime import datetime

import pandas as pd
import streamlit as st

# ---------- Переносим ключ GigaChat из secrets в переменную окружения ----------
# Сам ключ НИКОГДА не хранится в коде: он лежит в .streamlit/secrets.toml локально
# и в Secrets на Streamlit Cloud. Модуль ai.py читает os.environ["GIGA_AUTH_KEY"].
if "GIGA_AUTH_KEY" not in os.environ:
    try:
        os.environ["GIGA_AUTH_KEY"] = st.secrets["GIGA_AUTH_KEY"]
    except (FileNotFoundError, KeyError):
        pass  # без ключа приложение запустится, но чат скажет «ключ не найден»

from nexus import db
from nexus.core import (MALE, FEMALE, GOALS, LEVELS, EQUIPMENT,
                        Profile, bmi, bmi_category, calories, macros,
                        weekly_plan, meal_plan)
from nexus_ai import chat_tab
from nexus_auth import auth_screen, current_user, logout_button

st.set_page_config(page_title="Nexus Fitness", page_icon="nexus_logo.png", layout="wide")


# ---------- Авторизация ----------
user = current_user()
if user is None:
    auth_screen()
    st.stop()

SAFE_EMAIL = re.sub(r"[^a-z0-9_.@-]", "_", user["email"].lower())


# ---------- Данные: теперь через базу (nexus.db) ----------
def load_profile() -> Profile:
    data = db.get_profile(SAFE_EMAIL)
    if data:
        return Profile(**data)
    return Profile(name=user["name"])


def save_profile(p: Profile) -> None:
    db.save_profile(SAFE_EMAIL, p.__dict__)


def load_plan():
    plan = db.get_plan(SAFE_EMAIL)
    if not plan:
        return None
    # План с английскими названиями остался от старого датасета — пересобираем
    try:
        first_day = next(iter(plan.values()))
        if not first_day or any(str(ex.get("name", "")).isascii() for ex in first_day):
            return None
    except Exception:
        return None
    return plan


def save_plan(plan):
    db.save_plan(SAFE_EMAIL, plan)


def load_progress():
    return set(db.get_progress(SAFE_EMAIL) or [])


def save_progress(completed):
    db.save_progress(SAFE_EMAIL, list(completed))


# ---------- Разовый перенос старых JSON-файлов ----------
def _migrate_old_files():
    """Первый вход после перехода на базу: старые файлы переезжают в app.db."""
    import glob
    import json

    base = os.path.dirname(os.path.abspath(__file__))

    for path in glob.glob(os.path.join(base, "profile_*.json")):
        email = re.sub(r"^profile_|\.json$", "", os.path.basename(path))
        try:
            with open(path, encoding="utf-8") as f:
                db.save_profile(email, json.load(f))
        except Exception:
            pass

    for path in glob.glob(os.path.join(base, "workouts_*.json")):
        email = re.sub(r"^workouts_|\.json$", "", os.path.basename(path))
        try:
            with open(path, encoding="utf-8") as f:
                db.save_plan(email, json.load(f))
        except Exception:
            pass

    for path in glob.glob(os.path.join(base, "progress_*.json")):
        email = re.sub(r"^progress_|\.json$", "", os.path.basename(path))
        try:
            with open(path, encoding="utf-8") as f:
                db.save_progress(email, json.load(f))
        except Exception:
            pass


# Переносим один раз: если профиля в базе ещё нет — пробуем миграцию
if not db.get_profile(SAFE_EMAIL):
    _migrate_old_files()


p = load_profile()

# Прогресс сбрасываем при смене пользователя в рамках одной сессии
if st.session_state.get("completed_for") != SAFE_EMAIL:
    st.session_state["completed_exercises"] = load_progress()
    st.session_state["completed_for"] = SAFE_EMAIL


if os.path.exists("nexus_logo.png"):
    col1, col2 = st.columns([1, 8])
    with col1:
        st.image("nexus_logo.png", width=120)
    with col2:
        st.markdown("### Nexus Fitness")
        st.caption("Твой персональный ИИ‑тренер и трекер прогресса")
else:
    st.markdown("### Nexus Fitness")
    st.caption("Твой персональный ИИ‑тренер и трекер прогресса (логотип не найден)")

# ---------- Боковая панель: аккаунт и профиль ----------
with st.sidebar:
    st.header(f"👤 {user['name']}")
    st.caption(user["email"])
    logout_button()
    st.divider()

    st.header("Ваш профиль")
    p.name = st.text_input("Имя", p.name or "Атлет")
    p.sex = st.radio("Пол", [MALE, FEMALE], index=[MALE, FEMALE].index(p.sex))
    p.age = st.slider("Возраст", 14, 90, p.age)
    p.height = st.slider("Рост, см", 130, 220, p.height)
    p.weight = st.slider("Вес, кг", 35.0, 200.0, p.weight, 0.5)
    p.goal = st.select_slider("Цель", GOALS, value=p.goal)
    p.level = st.select_slider("Уровень", LEVELS, value=p.level)
    p.days_per_week = st.select_slider("Тренировок в неделю", list(range(2, 6)), value=min(p.days_per_week, 5))
    p.equipment = st.select_slider("Инвентарь", EQUIPMENT, value=p.equipment)
    if st.button("💾 Сохранить профиль", use_container_width=True):
        save_profile(p)
        st.success("Профиль сохранён")

kcal = calories(p)
bmi_v = bmi(p)

# ---------- Табы ----------
tab_w, tab_n, tab_p, tab_ai = st.tabs(
    ["Тренировки", "Питание", "Прогресс", "ИИ-тренер"]
)

# ---------- Вкладка «Тренировки» ----------
with tab_w:
    st.subheader(f"План недели: {p.goal}, {p.level.lower()}")
    st.caption(f"Целевая нагрузка: {p.days_per_week} тренировки в неделю · инвентарь: {p.equipment.lower()}")

    plan = load_plan()
    if plan is None:
        plan = weekly_plan(p)
        save_plan(plan)

    if st.button("🔄 Пересобрать план", use_container_width=True):
        plan = weekly_plan(p)
        save_plan(plan)
        st.rerun()

    for day, exercises in plan.items():
        with st.expander(day, expanded=(day == list(plan)[0])):
            col_ic, col_day = st.columns([1, 20])
            with col_ic:
                st.image("days_photo.png.png", width=24)
            with col_day:
                st.markdown(f"**{day}**")

            total = len(exercises)
            for ex in exercises:
                name = ex["name"]
                sets_txt = f"{ex['sets']} подхода × {ex['reps']} повторений, отдых {ex['rest']}"
                checked = st.checkbox(
                    f"**{name}** — {sets_txt}",
                    key=f"chk_{day}_{name}",
                    value=name in st.session_state["completed_exercises"],
                )
                if checked:
                    st.session_state["completed_exercises"].add(name)
                else:
                    st.session_state["completed_exercises"].discard(name)

            done = sum(1 for ex in exercises if ex["name"] in st.session_state["completed_exercises"])
            st.progress(done / total, text=f"Выполнено {done} из {total}")

    save_progress(st.session_state["completed_exercises"])

    with st.expander("⏱️ Таймер отдыха"):
        if st.button("Отдых 60 секунд", use_container_width=True):
            bar = st.progress(0)
            for i in range(60):
                bar.progress((i + 1) / 60, text=f"Осталось {60 - i} с")
                time.sleep(1)
            st.success("Отдых закончен — вперёд!")

# ---------- Вкладка «Питание» ----------
with tab_n:
    st.subheader(f"Цель: {kcal} ккал в день")
    m = macros(p, kcal)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Калории", f"{kcal}")
    c2.metric("Белки", f"{m['белки']} г")
    c3.metric("Жиры", f"{m['жиры']} г")
    c4.metric("Углеводы", f"{m['углеводы']} г")
    st.bar_chart(pd.DataFrame({"ккал": {"Белки": m["белки"] * 4,
                                        "Жиры": m["жиры"] * 9,
                                        "Углеводы": m["углеводы"] * 4}}))
    st.subheader("Примерное меню на день")
    for meal, dish in meal_plan(p).items():
        st.markdown(f"**{meal}:** {dish}")

# ---------- Вкладка «Прогресс» ----------
with tab_p:
    st.subheader("Динамика веса")
    if p.weight_history:
        df = pd.DataFrame(p.weight_history, columns=["Дата", "Вес"])
        df = df.set_index("Дата")
        st.line_chart(df)
        first, last = df["Вес"].iloc[0], df["Вес"].iloc[-1]
        diff = last - first
        arrow = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
        st.metric("Изменение", f"{diff:+.1f} кг", f"{arrow}")
    else:
        st.info("Пока нет замеров — добавьте первый ниже")
    col1, col2 = st.columns([2, 1])
    d = col1.text_input("Дата (дд.мм.гггг)", datetime.now().strftime("%d.%m.%Y"))
    w = col2.number_input("Вес, кг", 35.0, 200.0, p.weight, 0.5)
    if st.button("Записать замер"):
        p.weight_history = p.weight_history + [(d, w)]
        save_profile(p)
        st.rerun()
    st.subheader("ИМТ")
    st.metric("ИМТ", f"{bmi_v:.1f}", bmi_category(bmi_v))

# ---------- Вкладка «ИИ-тренер» ----------
with tab_ai:
    chat_tab(p)
