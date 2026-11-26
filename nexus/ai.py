"""Логика ИИ-тренера Nexus: GigaChat, промпты, стриминг.

Чистый модуль без Streamlit: интерфейс (кнопки, история, карточки)
живёт в nexus_ai.py.
"""

import json
import os
import time
import uuid

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://api.giga.chat/v1/chat/completions"
MODEL = "GigaChat-2"

SYSTEM_PROMPT = """Ты — ИИ-тренер приложения Nexus Fitness. Отвечай на русском языке,
кратко, дружелюбно и по делу. Ты знаешь профиль пользователя и даёшь советы
с его учётом: тренировки, питание, восстановление, мотивация, техника упражнений.

Правила:
- Обращайся к врачу ТОЛЬКО при травме, боли, заболевании или подозрении на них.
  Здоровый пользователь любого возраста (в том числе подросток) НЕ нуждается
  в рекомендациях врача — не советуй врача без причины и не отказывайся
  отвечать на вопросы о тренировках.
- Тренировки для подростков — нормальная и полезная тема. Отвечай по существу:
  программа, упражнения, восстановление. Для несовершеннолетних (до 18 лет)
  рекомендуй умеренные веса, технику под контролем взрослого/тренера
  и без работы «до отказа» с большими весами — но это встроено в советы,
  а не повод отправить к врачу.
- Не предлагай экстремальные диеты. Для набора массы давай обычные
  рекомендации: профицит калорий, белок, сон, прогрессия нагрузок.
- Если пользователь просит изменить программу — давай конкретные
  рекомендации (дни, упражнения, веса), которые он сможет внести
  в профиль на боковой панели приложения.
- Не предлагай гифки, видео или просмотр базы упражнений — описывай технику словами.

Про технику упражнений: описывай выполнение сам, по шагам, на русском языке —
исходное положение, движение, дыхание, типичные ошибки новичка. Учитывай уровень
и инвентарь пользователя из профиля. Не отправляй пользователя в базу упражнений —
ты сам источник описаний. Упражнения в тексте называй привычными русскими именами
(«жим штанги лёжа», «тяга верхнего блока», «приседания со штангой»)."""

_TOKEN_CACHE = {"token": None, "exp": 0.0}


def _profile_text(p) -> str:
    """Превращает профиль пользователя в текст для промпта."""
    parts = []
    for field, label in (
        ("name", "Имя"),
        ("sex", "Пол"),
        ("age", "Возраст"),
        ("height", "Рост (см)"),
        ("weight", "Вес (кг)"),
        ("goal", "Цель"),
        ("level", "Уровень"),
        ("days_per_week", "Тренировок в неделю"),
        ("equipment", "Инвентарь"),
    ):
        value = getattr(p, field, None)
        if value not in (None, ""):
            parts.append(f"{label}: {value}")
    return "; ".join(parts) if parts else "профиль не заполнен"


def _build_messages(p, history):
    """Собирает сообщения: системный промпт + профиль + последние 20 сообщений."""
    system = SYSTEM_PROMPT + "\n\nПрофиль пользователя: " + _profile_text(p)
    messages = [{"role": "system", "content": system}]
    for m in history[-20:]:
        messages.append({"role": m["role"], "content": m["content"]})
    return messages


def _get_token() -> str:
    """Возвращает access-токен GigaChat, при необходимости обновляет его.

    Ключ берётся из переменной окружения GIGA_AUTH_KEY — её заполняет
    app.py из st.secrets.
    """
    now = time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["exp"]:
        return _TOKEN_CACHE["token"]

    auth_key = os.environ.get("GIGA_AUTH_KEY")
    if not auth_key:
        raise RuntimeError(
            "GIGA_AUTH_KEY не найден в переменных окружения. "
            "Проверьте блок в app.py, который переносит его из st.secrets."
        )
    resp = requests.post(
        OAUTH_URL,
        headers={
            "Authorization": f"Basic {auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "NexusFitness/1.0",
        },
        data={"scope": "GIGACHAT_API_PERS"},
        verify=False,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    _TOKEN_CACHE["token"] = data["access_token"]
    _TOKEN_CACHE["exp"] = now + 25 * 60
    return _TOKEN_CACHE["token"]


def _ask_giga_stream(p, history):
    """Стриминг ответа от GigaChat: отдаёт текст по кусочкам.

    Поток читаем как байты и декодируем в UTF-8 вручную — иначе
    requests декодирует его как latin-1 и русский текст ломается.
    """
    token = _get_token()
    payload = {
        "model": MODEL,
        "messages": _build_messages(p, history),
        "temperature": 0.7,
        "max_tokens": 800,
        "stream": True,
    }
    with requests.post(
        CHAT_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "NexusFitness/1.0",
        },
        json=payload,
        stream=True,
        verify=False,
        timeout=90,
    ) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines():
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace")
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except Exception:
                continue
            piece = chunk["choices"][0]["delta"].get("content") or ""
            if piece:
                yield piece
