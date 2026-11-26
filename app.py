"""Nexus Fitness — интерфейс на Streamlit. Запуск: streamlit run app.py"""

import json
import os
import re
import shutil
import time
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from nexus_core import (MALE, FEMALE, GOALS, LEVELS, EQUIPMENT,
                        Profile, bmi, bmi_category, calories, macros,
                        weekly_plan, meal_plan)
from nexus_ai import chat_tab
from nexus_auth import auth_screen, current_user, logout_button

# Файлы по умолчанию — после входа заменяются на персональные
PROFILE_FILE = "profile.json"
WORKOUTS_FILE = "workouts.json"
PROGRESS_FILE = "progress.json"

st.set_page_config(page_title="Nexus Fitness", page_icon="nexus_logo.png", layout="wide")

# ---------- Состояние интерфейса ----------
if "page" not in st.session_state:
    st.session_state["page"] = "ai"          # стартовый экран — ИИ-тренер
if "menu_open" not in st.session_state:
    st.session_state["menu_open"] = False    # панель по умолчанию закрыта

# ---------- Авторизация ----------
user = current_user()
if user is None:
    auth_screen()
    st.stop()

SAFE_EMAIL = re.sub(r"[^a-z0-9_.@-]", "_", user["email"].lower())
PROFILE_FILE = f"profile_{SAFE_EMAIL}.json"
WORKOUTS_FILE = f"workouts_{SAFE_EMAIL}.json"
PROGRESS_FILE = f"progress_{SAFE_EMAIL}.json"


def _migrate_old_files():
    """Первый вход: старые общие файлы переезжают этому пользователю."""
    for old, new in (("profile.json", PROFILE_FILE),
                     ("workouts.json", WORKOUTS_FILE),
                     ("progress.json", PROGRESS_FILE)):
        if os.path.exists(old) and not os.path.exists(new):
            try:
                shutil.copy(old, new)
            except Exception:
                pass


_migrate_old_files()


def load_profile() -> Profile:
    try:
        with open(PROFILE_FILE, encoding="utf-8") as f:
            return Profile(**json.load(f))
    except Exception:
        return Profile(name=user["name"])


def save_profile(p: Profile) -> None:
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(p.__dict__, f, ensure_ascii=False, indent=2)


def load_plan():
    if os.path.exists(WORKOUTS_FILE):
        try:
            with open(WORKOUTS_FILE, encoding="utf-8") as f:
                plan = json.load(f)
        except Exception:
            return None
        # План с английскими названиями остался от версии с датасетом — пересобираем
        try:
            first_day = next(iter(plan.values()))
            if not first_day or any(str(ex.get("name", "")).isascii() for ex in first_day):
                return None
        except Exception:
            return None
        return plan
    return None


def save_plan(plan):
    with open(WORKOUTS_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_progress(completed):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(completed), f, ensure_ascii=False)


p = load_profile()

# Прогресс сбрасываем при смене пользователя в рамках одной сессии
if st.session_state.get("completed_for") != SAFE_EMAIL:
    st.session_state["completed_exercises"] = load_progress()
    st.session_state["completed_for"] = SAFE_EMAIL


# ---------- CSS: плавно выдвижная панель на 75% экрана ----------
# Состояние панели задаёт Python: transform меняется при перерисовке страницы,
# и CSS-переход проигрывается, потому что элемент панели существует всегда.
# Затемнением управляет JavaScript — по невидимому маркеру data-open,
# в котором Python сообщает актуальное состояние панели.
def _inject_css(menu_open: bool) -> None:
    transform = "translateX(0)" if menu_open else "translateX(-100%)"
    css = (
        "<style>"
        'section[data-testid="stSidebar"]{width:75vw !important;min-width:75vw !important;'
        'max-width:75vw !important;position:fixed !important;top:0 !important;left:0 !important;'
        'height:100vh !important;z-index:100000 !important;'
        f'transform:{transform} !important;'
        'transition:transform 0.35s cubic-bezier(0.4,0,0.2,1) !important;'
        'box-shadow:8px 0 40px rgba(0,0,0,0.25);}'
        'section[data-testid="stSidebar"] + div{margin-left:0 !important;}'
        'section[data-testid="stSidebar"] ~ div{margin-left:0 !important;}'
        'div[data-testid="stMain"]{margin-left:0 !important;}'
        '[data-testid="stSidebarCollapseButton"],[data-testid="stSidebarCollapsedControl"]'
        '{display:none !important;}'
        '.nexus-overlay{position:fixed;top:0;left:0;width:100vw;height:100vh;'
        'background:rgba(0,0,0,0.4);z-index:99999;opacity:0;'
        'transition:opacity 0.35s ease;pointer-events:auto;cursor:pointer;}'
        "</style>"
        # Невидимый маркер: JavaScript по нему понимает, открыта панель или закрыта
        f'<div id="nexus-panel-state" data-open="{1 if menu_open else 0}" style="display:none"></div>'
    )
    st.markdown(css, unsafe_allow_html=True)


_MENU_SCRIPT = """
<script>
(function() {
    var doc = window.parent.document;
    // Скрипт должен выполниться ровно один раз: документ живёт постоянно,
    // а его обработчики переживают любые перерисовки Streamlit.
    if (window.__nexusMenuBound) return;
    window.__nexusMenuBound = true;

    function ensureBurger() {
        var b = doc.getElementById('nexus-burger');
        if (b) return b;
        b = doc.createElement('div');
        b.id = 'nexus-burger';
        b.textContent = '☰';
        b.setAttribute('style', [
            'position:fixed','top:12px','left:12px','width:44px','height:44px',
            'border-radius:999px','background:#1f2430',
            'border:1px solid rgba(255,255,255,0.15)',
            'box-shadow:0 2px 10px rgba(0,0,0,0.25)',
            'display:flex','align-items:center','justify-content:center',
            'font-size:20px','line-height:1','cursor:pointer',
            'color:#ffffff','user-select:none','pointer-events:auto','z-index:2147483000'
        ].join(';'));
        doc.body.appendChild(b);
        return b;
    }

    function findMenuButton() {
        var btns = doc.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            var t = btns[i].textContent || '';
            if (t.indexOf('☰') !== -1) return btns[i];
        }
        return null;
    }

    function ensureOverlay() {
        var ov = doc.querySelector('.nexus-overlay');
        if (!ov) {
            ov = doc.createElement('div');
            ov.className = 'nexus-overlay';
            ov.style.opacity = '0';
            doc.body.appendChild(ov);
            requestAnimationFrame(function() { ov.style.opacity = '1'; });
        } else if (ov._closing) {
            // Пользователь успел снова открыть панель до конца анимации закрытия
            ov._closing = false;
            if (ov._t) { clearTimeout(ov._t); ov._t = null; }
            ov.style.opacity = '1';
        }
        return ov;
    }

    function closeOverlay() {
        var ov = doc.querySelector('.nexus-overlay');
        if (ov && !ov._closing) {
            ov._closing = true;
            ov.style.opacity = '0';
            ov._t = setTimeout(function() {
                if (ov.parentNode) ov.parentNode.removeChild(ov);
            }, 400);
        }
    }

    function isOpen() {
        var marker = doc.getElementById('nexus-panel-state');
        return !!(marker && marker.getAttribute('data-open') === '1');
    }

    function sync() {
        ensureBurger();
        // Затемнением управляем строго по маркеру: панель открыта — overlay есть,
        // закрыта — overlay плавно гаснет. Раньше смотрели на инлайновый
        // style.transform, которого не существует — отсюда вечное затемнение.
        if (isOpen()) {
            ensureOverlay();
        } else {
            closeOverlay();
        }
        var btn = findMenuButton();
        if (!btn) return;
        var col = btn.closest('div[data-testid="stColumn"]');
        if (col && col.style.visibility !== 'hidden') {
            col.style.visibility = 'hidden';
        }
    }

    // Делегирование: ловим клики на самом документе, поэтому обработчик
    // работает и с гамбургером, и с заново созданным затемнением после перерисовок.
    doc.addEventListener('click', function(e) {
        var t = e.target;
        var hitBurger = t && (t.id === 'nexus-burger' || (t.closest && t.closest('#nexus-burger')));
        var hitOverlay = isOpen() && t &&
            ((t.classList && t.classList.contains('nexus-overlay')) ||
             (t.closest && t.closest('.nexus-overlay')));
        if (hitBurger || hitOverlay) {
            var btn = findMenuButton();
            if (btn) btn.click();
        }
    }, true);

    // Следим за перерисовками: обновляем затемнение и прячем оригинальную кнопку.
    var obs = new MutationObserver(sync);
    obs.observe(doc.body, {childList: true, subtree: true});
    sync();
})();
</script>
"""


def _mount_menu_script() -> None:
    components.html(_MENU_SCRIPT, height=0)


_inject_css(st.session_state["menu_open"])
_mount_menu_script()

# ---------- Кнопка-гамбургер в левом верхнем углу ----------
# Оригинал рендерим, но прячем скриптом; видимая кнопка — плавающий гамбургер.
col_btn, col_rest = st.columns([0.06, 0.94])
with col_btn:
    if st.button("☰", key="menu_btn"):
        st.session_state["menu_open"] = not st.session_state["menu_open"]
        st.rerun()

# ---------- Навигация ----------
NAV = [
    ("ai",       "🤖 ИИ-тренер"),
    ("workouts", "🏋️ Тренировки"),
    ("nutrition", "🥗 Питание"),
    ("progress", "📈 Прогресс"),
    ("profile",  "👤 Профиль"),
]

# Содержимое панели рисуем ВСЕГДА: при закрытой панели она уехана за левый край
# экрана (translateX(-100%)) и не видна, зато элемент панели не пересоздаётся
# при закрытии — анимация работает плавно на всех вкладках.
with st.sidebar:
    st.markdown("### Nexus Fitness")
    st.caption(f"{user['name']} · {user['email']}")
    logout_button()
    st.divider()
    for key, label in NAV:
        if st.button(label, key=f"nav_{key}", use_container_width=True):
            st.session_state["page"] = key
            st.session_state["menu_open"] = False
            st.rerun()

page = st.session_state["page"]

# ---------- Стартовый экран: ИИ-тренер на весь экран ----------
if page == "ai":
    h = datetime.now().hour
    if h < 5:
        hello = "Доброй ночи"
    elif h < 12:
        hello = "Доброе утро"
    elif h < 18:
        hello = "Добрый день"
    else:
        hello = "Добрый вечер"
    first_name = user["name"].split()[0]

    st.markdown(
        f"""
        <div style="text-align:center; margin-top: 8vh;">
            <h1 style="font-weight: 700; margin-bottom: 0.2em;">{hello}, {first_name}!</h1>
            <p style="font-size: 1.1rem; opacity: 0.7;">
                Чем займёмся сегодня — тренировка, питание или пара вопросов?
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    chat_tab(p)

# ---------- Страница «Тренировки» ----------
elif page == "workouts":
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
        with st.expander(f"📅 {day}", expanded=(day == list(plan)[0])):
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

# ---------- Страница «Питание» ----------
elif page == "nutrition":
    kcal = calories(p)
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

# ---------- Страница «Прогресс» ----------
elif page == "progress":
    bmi_v = bmi(p)
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

# ---------- Страница «Профиль» ----------
elif page == "profile":
    st.subheader("Ваш профиль")
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
    bmi_v = bmi(p)
    st.metric("ИМТ", f"{bmi_v:.1f}", bmi_category(bmi_v))
