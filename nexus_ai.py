"""ИИ-тренер Nexus: интерфейс чата (Streamlit). Логика — в nexus/ai.py."""

import os

import streamlit as st

import nexus_library
from nexus import ai, db

CHAT_STYLE = """
<style>
    /* ---- Аватары: перебираем все известные варианты testid ---- */
    [data-testid="stChatMessageAvatarContainer"],
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="stChatMessageAvatar"],
    .stAvatar,
    [data-testid="stChatMessage"] [data-testid="stImage"] {
        display: none !important;
    }

    /* ---- Сообщения без «пузырей» + мягкое появление ---- */
    [data-testid="stChatMessage"] {
        background: transparent;
        border: none;
        box-shadow: none;
        padding: 0 0 6px 0;
        animation: nexusFadeIn 0.3s ease-out;
    }

    @keyframes nexusFadeIn {
        from { opacity: 0; transform: translateY(6px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    /* ---- Сброс прежней прямоугольной рамки у внешних контейнеров ---- */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* ---- Сама пилюля: теперь рамка только на внутреннем поле ---- */
    [data-testid="stChatInputPrimary"] {
        border: 1px solid rgba(120, 120, 120, 0.35) !important;
        border-radius: 999px !important;
        padding: 2px 16px !important;
        min-height: 34px;
        align-items: center;
    }
    [data-testid="stChatInputPrimary"]:focus-within {
        border-color: #29b092 !important;
    }
    [data-testid="stChatInput"] textarea {
        font-size: 0.95rem;
    }

    /* ---- Круглая кнопка отправки справа ---- */
    [data-testid="stChatInputSubmitButton"] {
        width: 34px;
        height: 34px;
        min-width: 34px;
        border-radius: 999px !important;
        background: #29b092 !important;
        color: #ffffff !important;
        margin-left: 8px;
        flex-shrink: 0;
    }
    [data-testid="stChatInputSubmitButton"] svg {
        fill: #ffffff !important;
        color: #ffffff !important;
    }
    [data-testid="stChatInputSubmitButton"]:hover {
        background: #23937c !important;
    }

    /* выравниваем пилюлю и кнопку в одну линию */
    [data-testid="stChatInput"] > div {
        gap: 8px;
        align-items: center;
    }
</style>
"""

MAX_CARDS = 3  # максимум карточек упражнений под одним ответом


def _safe_email():
    """Почта текущего пользователя в безопасном для хранения виде."""
    try:
        from nexus_auth import current_user
        user = current_user()
        if user and user.get("email"):
            import re
            return re.sub(r"[^a-z0-9_.@-]", "_", user["email"].lower())
    except Exception:
        pass
    return "guest"


def _new_chat():
    return {"id": str(__import__("uuid").uuid4()), "title": "Новый чат", "history": []}


def _ensure_state():
    """Загружает чаты пользователя из базы при смене аккаунта."""
    email = _safe_email()
    if st.session_state.get("chats_for") != email:
        chats = db.get_chats(email)
        st.session_state["chats"] = chats if chats else [_new_chat()]
        st.session_state["chats_for"] = email
    if not st.session_state["chats"]:
        st.session_state["chats"] = [_new_chat()]
    if "current_chat_id" not in st.session_state or \
       st.session_state["current_chat_id"] not in [c["id"] for c in st.session_state["chats"]]:
        st.session_state["current_chat_id"] = st.session_state["chats"][0]["id"]


# ---------- Карточки упражнений из локального датасета ----------

@st.cache_data(show_spinner=False)
def _name_index():
    """[(строка-триггер, упражнение)] — по всей базе, отсортировано от длинных к коротким."""
    pairs = []
    for ex in nexus_library.load_exercises():
        name = str(ex.get("name", "")).lower().strip()
        if not name:
            continue
        pairs.append((name, ex))
        ru = nexus_library.get_display_name(name)
        # длинные русские названия — триггеры; короткие слова дают ложные срабатывания
        if len(ru) >= 8:
            pairs.append((ru.lower(), ex))
    pairs.sort(key=lambda t: -len(t[0]))
    return pairs


def _find_exercises_in_text(text: str) -> list:
    """Находит в тексте упомянутые упражнения из базы. Максимум MAX_CARDS."""
    haystack = " " + str(text).lower().replace("ё", "е") + " "
    found, seen = [], set()
    try:
        pairs = _name_index()
    except Exception:
        return []
    for trigger, ex in pairs:
        if ex["name"] in seen:
            continue
        if trigger in haystack:
            seen.add(ex["name"])
            found.append(ex)
            if len(found) >= MAX_CARDS:
                break
    return found


def _show_cards(text: str):
    """Рисует под ответом карточки с гифками упомянутых упражнений."""
    matches = _find_exercises_in_text(text)
    for ex in matches:
        title = nexus_library.get_display_name(ex.get("name", "?"))
        with st.expander(f"🎬 {title} — техника на видео", expanded=False):
            st.caption(
                f"{nexus_library.get_target_ru(ex.get('target', ''))} · "
                f"{nexus_library.get_equipment_ru(ex.get('equipment', ''))}"
            )
            gif_path = os.path.join(
                nexus_library._DATASET_DIR, str(ex.get("gif_url", ""))
            )
            if gif_path and os.path.exists(gif_path):
                st.image(gif_path)
            steps = nexus_library._get_ru_steps(ex)
            if steps:
                st.markdown("**Эталонная техника из базы:**")
                for i, step in enumerate(steps, 1):
                    st.markdown(f"{i}. {step}")


def chat_tab(p):
    st.markdown(CHAT_STYLE, unsafe_allow_html=True)
    st.subheader("🤖 ИИ-тренер Nexus")
    st.caption("Каждый чат — отдельный диалог с тренером. История сохраняется автоматически.")
    _ensure_state()

    email = _safe_email()
    chats = st.session_state["chats"]

    # ----- Боковая панель: управление чатами -----
    with st.sidebar:
        st.markdown("### 💬 Чаты")
        if st.button("➕ Новый чат", use_container_width=True):
            fresh = _new_chat()
            chats.insert(0, fresh)
            st.session_state["current_chat_id"] = fresh["id"]
            db.save_chat(email, fresh)
            st.rerun()

        ids = [c["id"] for c in chats]
        cur_idx = ids.index(st.session_state["current_chat_id"])
        sel = st.selectbox(
            "Выберите чат",
            options=range(len(ids)),
            index=cur_idx,
            format_func=lambda i: chats[i]["title"],
            label_visibility="collapsed",
        )
        if ids[sel] != st.session_state["current_chat_id"]:
            st.session_state["current_chat_id"] = ids[sel]
            st.rerun()

        if st.button("🗑 Удалить текущий чат", use_container_width=True):
            removed = chats.pop(cur_idx)
            db.delete_chat(email, removed["id"])
            st.session_state["chats"] = chats if chats else [_new_chat()]
            st.session_state["current_chat_id"] = st.session_state["chats"][0]["id"]
            db.save_chat(email, st.session_state["chats"][0])
            st.rerun()

    # ----- Основная область: переписка -----
    current = next(c for c in chats if c["id"] == st.session_state["current_chat_id"])
    st.caption(f"💬 {current['title']}")

    for msg in current["history"]:
        with st.chat_message("user" if msg["role"] == "user" else "assistant"):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _show_cards(msg["content"])

    question = st.chat_input("Спросите: «как делать становую тягу?» или «составлю план на 4 дня?»")
    if not question:
        return

    current["history"].append({"role": "user", "content": question})
    if current["title"] == "Новый чат":
        current["title"] = question[:40] + ("…" if len(question) > 40 else "")
    db.save_chat(email, current)

    # вопрос сразу появляется в чате, без ожидания
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        response = ""
        try:
            for piece in ai._ask_giga_stream(p, current["history"]):
                response += piece
                placeholder.markdown(response + "▌")
        except Exception as e:
            if response:
                # ответ успел начаться — сохраняем то, что пришло
                current["history"].append({"role": "assistant", "content": response})
                db.save_chat(email, current)
                st.error(f"Связь оборвалась. Сохранён частичный ответ. ({e})")
            else:
                current["history"].pop()  # убираем «висящий» вопрос
                st.error(f"Не удалось получить ответ: {e}. Проверьте ключ в secrets.toml и интернет.")
            return
        placeholder.markdown(response)

    current["history"].append({"role": "assistant", "content": response})
    db.save_chat(email, current)
    _show_cards(response)
