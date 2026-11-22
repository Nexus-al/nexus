"""База упражнений — работает поверх датасета exercises-dataset."""

import json
import os
import re

import streamlit as st

_DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exercises-dataset")
_JSON_PATH = os.path.join(_DATASET_DIR, "data", "exercises.json")

# ---------- Русские названия для избранных упражнений (точные совпадения) ----------
DISPLAY_NAMES = {
    "barbell full squat": "Приседания со штангой",
    "barbell bench press": "Жим штанги лёжа",
    "romanian deadlift": "Румынская тяга",
    "pull-up": "Подтягивания",
    "push-up": "Отжимания",
    "dumbbell lateral raise": "Махи гантелями в стороны",
    "dumbbell biceps curl": "Подъём гантелей на бицепс",
    "lat pulldown": "Тяга верхнего блока",
    "plank": "Планка",
    "leg press": "Жим ногами",
    "bodyweight squat": "Приседания без веса",
    "dumbbell lunge": "Выпады с гантелями",
    "deadlift": "Становая тяга",
    "bent over barbell row": "Тяга штанги в наклоне",
    "dumbbell shoulder press": "Жим гантелей над головой",
    "crunch": "Скручивания",
    "burpee": "Бёрпи",
}

# ---------- Автоперевод названий по словам ----------
RU_WORDS = {
    "sit-up": "скручивания", "sit-ups": "скручивания",
    "pull-up": "подтягивания", "pull-ups": "подтягивания",
    "chin-up": "подтягивания обратным хватом", "chin-ups": "подтягивания обратным хватом",
    "push-up": "отжимания", "push-ups": "отжимания", "pushup": "отжимания", "pushups": "отжимания",
    "skullcrusher": "французский жим", "skullcrushers": "французский жим",
    "barbell": "штанга", "dumbbell": "гантель", "dumbbells": "гантели",
    "kettlebell": "гиря", "cable": "блок", "machine": "тренажёр",
    "smith": "машина Смита", "leverage": "рычажный", "band": "резинка",
    "bench": "скамья", "incline": "наклонная", "decline": "обратный наклон",
    "press": "жим", "squat": "приседания", "squats": "приседания",
    "deadlift": "становая тяга", "romanian": "румынская", "bulgarian": "болгарские",
    "lunge": "выпады", "lunges": "выпады", "row": "тяга", "rows": "тяга",
    "pull": "тяга", "pulldown": "тяга блока", "lat": "широчайшие",
    "curl": "сгибание", "curls": "сгибание",
    "extension": "разгибание", "extensions": "разгибание",
    "raise": "подъём", "raises": "подъёмы", "lateral": "в стороны",
    "fly": "разводка", "flies": "разводка", "shrug": "шраги", "shrugs": "шраги",
    "crunch": "скручивания", "crunches": "скручивания", "plank": "планка",
    "burpee": "бёрпи", "burpees": "бёрпи", "treadmill": "беговая дорожка",
    "jump": "прыжки", "rope": "скакалка", "dip": "отжимания на брусьях", "dips": "отжимания на брусьях",
    "abs": "пресс", "chest": "грудь", "back": "спина",
    "shoulder": "плечи", "shoulders": "плечи",
    "legs": "ноги", "leg": "ноги", "arms": "руки", "arm": "руки",
    "biceps": "бицепс", "triceps": "трицепс",
    "quadriceps": "квадрицепс", "hamstrings": "бицепс бедра",
    "glutes": "ягодицы", "glute": "ягодицы", "calves": "икры", "calf": "икры",
    "forearm": "предплечья", "forearms": "предплечья", "wrist": "запястья",
    "neck": "шея", "hips": "бёдра", "hip": "бедро", "core": "кор",
    "overhead": "над головой", "weighted": "с весом", "assisted": "с поддержкой",
    "run": "бег", "running": "бег", "bike": "велотренажёр",
    "reverse": "обратные", "seated": "сидя", "standing": "стоя", "lying": "лёжа",
    "single": "одноногая", "alternating": "поочерёдные", "side": "боковые",
    "close-grip": "узким хватом", "wide-grip": "широким хватом", "grip": "хватом",
    "full": "полные", "stretching": "растяжка",
}

CATEGORY_RU = {
    "upper arms": "Руки (верх)", "lower arms": "Руки (низ)",
    "upper legs": "Ноги (верх)", "lower legs": "Ноги (низ)",
    "chest": "Грудь", "back": "Спина", "shoulders": "Плечи",
    "waist": "Пресс и кор", "cardio": "Кардио", "neck": "Шея",
}

EQUIPMENT_RU = {
    "body weight": "собственный вес", "barbell": "штанга", "dumbbell": "гантель",
    "cable": "блок", "leverage machine": "тренажёр", "smith machine": "машина Смита",
    "band": "резинка", "kettlebell": "гиря", "weighted": "утяжеление",
    "stability ball": "фитбол", "ez barbell": "EZ-штанга", "other": "другое",
}

TARGET_RU = {
    "abs": "пресс", "biceps": "бицепс", "triceps": "трицепс",
    "pectoralis major": "грудные", "delts": "дельты", "deltoids": "дельты",
    "glutes": "ягодицы", "quadriceps": "квадрицепс",
    "hamstrings": "задняя поверхность бедра", "calves": "икры",
    "lats": "широчайшие", "traps": "трапеции", "forearms": "предплечья",
    "lower back": "поясница", "hip flexors": "сгибатели бедра",
}

# ---------- Поисковый словарь: русская фраза/корень -> английские ключевые слова ----------
# Сначала более длинные фразы (они перехватываются раньше коротких корней).
RU_SEARCH = [
    ("жим штанги лежа", ["barbell bench press"]),
    ("жим гантелей лежа", ["dumbbell bench press"]),
    ("жим на наклонной скамье", ["incline bench press"]),
    ("жим на наклонной", ["incline bench press"]),
    ("жим лежа", ["bench press"]),
    ("жим ногами", ["leg press"]),
    ("жим стоя", ["overhead press", "military press"]),
    ("жим сидя", ["shoulder press"]),
    ("жим над головой", ["overhead press"]),
    ("жим вверх", ["overhead press"]),
    ("жим гантелей", ["dumbbell press", "shoulder press"]),
    ("жим штанги", ["barbell press", "bench press"]),
    ("жим кроссовером", ["cable crossover"]),
    ("французский жим", ["skullcrusher", "triceps extension"]),
    ("тяга штанги в наклоне", ["bent over barbell row"]),
    ("тяга гантели в наклоне", ["dumbbell bent over row"]),
    ("тяга гантели", ["dumbbell row"]),
    ("тяга нижнего блока", ["seated cable row"]),
    ("тяга горизонтального блока", ["seated cable row"]),
    ("тяга верхнего блока", ["lat pulldown"]),
    ("тяга вертикального блока", ["lat pulldown"]),
    ("тяга к поясу", ["bent over row"]),
    ("румынская тяга", ["romanian deadlift"]),
    ("становая тяга", ["deadlift"]),
    ("бицепс бедра", ["hamstring", "leg curl"]),
    ("подъем на носки", ["calf raise"]),
    ("подъёмы на носки", ["calf raise"]),
    ("подъемы на носки", ["calf raise"]),
    ("разводка гантелей", ["dumbbell fly"]),
    ("скручивания на блоке", ["cable crunch"]),
    ("приседания в тренажере", ["squat machine", "hack squat"]),
    ("приседания со штангой", ["barbell full squat", "barbell squat"]),
    ("приседания без веса", ["bodyweight squat", "free squat"]),
    ("приседания сумо", ["sumo squat"]),
    ("подтягивания обратным хватом", ["chin-up"]),
    ("отжимания на брусьях", ["dip"]),
    ("отжимания от пола", ["push-up"]),
    ("гиперэкстензия", ["hyperextension"]),
    ("приседан", ["squat"]),
    ("подтягиван", ["pull-up", "chin-up"]),
    ("отжиман", ["push-up", "pushup", "dip"]),
    ("выпад", ["lunge"]),
    ("скакалк", ["rope", "jump"]),
    ("ягодиц", ["glute", "hip", "squat", "lunge", "deadlift"]),
    ("квадрицепс", ["quadriceps", "leg extension", "squat", "lunge"]),
    ("предплеч", ["forearm", "wrist"]),
    ("планка", ["plank"]),
    ("пресс", ["abs", "crunch", "sit-up", "core"]),
    ("живот", ["abs", "crunch", "sit-up"]),
    ("кор", ["core", "abs", "plank"]),
    ("груд", ["chest", "pectoral", "bench", "fly", "push-up"]),
    ("спин", ["back", "row", "pull-up", "pulldown", "deadlift"]),
    ("бицепс", ["biceps", "curl"]),
    ("трицепс", ["triceps", "extension", "pushdown", "skullcrusher", "dip"]),
    ("плеч", ["shoulder", "raise", "press", "shrug"]),
    ("шраг", ["shrug"]),
    ("брусь", ["dip"]),
    ("голен", ["calf", "calves"]),
    ("разводк", ["fly"]),
    ("сгибан", ["curl"]),
    ("разгибан", ["extension"]),
    ("приведен", ["adduction"]),
    ("отведен", ["abduction"]),
    ("ног", ["squat", "lunge", "leg", "deadlift", "calf"]),
    ("тяг", ["row", "pulldown", "pull"]),
    ("жим", ["press"]),
    ("бег", ["run", "treadmill", "cardio"]),
    ("икр", ["calf", "calves"]),
    ("руки", ["arm", "biceps", "triceps"]),
    ("шея", ["neck"]),
]


def _norm(s: str) -> str:
    """Приводит текст к сравнимому виду: нижний регистр, ё->е, без лишних знаков."""
    s = str(s).lower().replace("ё", "е")
    s = re.sub(r"[^\wа-яa-z\- ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


_stem_cache = {}


def _stem(w: str) -> str:
    """Обрезает русское окончание: тяга->тяг, приседания->приседан."""
    if len(w) > 4:
        for suf in ("иями", "ями", "ами", "ов", "ев", "ий", "ые", "ая", "ое",
                    "а", "я", "ы", "и", "е", "у", "ю", "о"):
            if w.endswith(suf) and len(w) - len(suf) >= 4:
                w = w[: -len(suf)]
                break
    return w


_reverse_index = None


def get_display_name(en_name: str) -> str:
    """Точное русское название, если есть; иначе перевод по словам."""
    key = str(en_name).lower().strip()
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    return " ".join(RU_WORDS.get(w, w) for w in key.split())


def get_category_ru(category: str) -> str:
    return CATEGORY_RU.get(str(category).lower(), category)


def get_equipment_ru(equipment: str) -> str:
    key = str(equipment).lower().strip()
    if key in EQUIPMENT_RU:
        return EQUIPMENT_RU[key]
    return " ".join(RU_WORDS.get(w, w) for w in key.split())


def get_target_ru(target: str) -> str:
    key = str(target).lower().strip()
    if key in TARGET_RU:
        return TARGET_RU[key]
    return " ".join(RU_WORDS.get(w, w) for w in key.split())


def search_keywords(query: str) -> list:
    """Переводит русский запрос в список английских ключевых слов."""
    q = _norm(query)
    if not q:
        return []
    # латиница — ищем как есть
    if re.search(r"[a-z]", q):
        return [q]
    found = []
    # сначала фразы из словаря
    for ru, ens in RU_SEARCH:
        if ru in q:
            found.extend(ens)
    # затем каждое слово отдельно: наращиваем ключи по корню
    for w in q.split():
        st_ = _stem_cache.setdefault(w, _stem(w))
        for ru, ens in RU_SEARCH:
            if st_ in ru:
                found.extend(ens)
    return list(dict.fromkeys(found))  # убираем дубли, сохраняя порядок


@st.cache_data
def load_exercises():
    """Загружает и кеширует весь датасет (читается с диска один раз)."""
    with open(_JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_ru_steps(ex: dict) -> list:
    """Русские шаги: сначала instruction_steps.ru (список), потом режем строку."""
    steps = (ex.get("instruction_steps") or {}).get("ru")
    if isinstance(steps, list) and steps:
        return steps
    text = (ex.get("instructions") or {}).get("ru")
    if isinstance(text, str) and text.strip():
        parts = [s.strip() for s in re.split(r"(?<=\.)\s+", text.strip()) if s.strip()]
        return parts
    return []


def find_exercise(ru_name: str):
    """Ищет упражнение в базе: фразы-словарь, затем токенный поиск по всей базе."""
    name = _norm(ru_name)
    if not name:
        return None
    exercises = load_exercises()

    # 1) если в плане английское название — пробуем прямое совпадение
    if re.search(r"[a-z]", name):
        for ex in exercises:
            if str(ex.get("name", "")).lower().strip() == name:
                return ex

    # 2) точное совпадение русского названия через обратный словарь
    global _reverse_index
    if _reverse_index is None:
        _reverse_index = {_norm(v): k for k, v in DISPLAY_NAMES.items()}
    en_exact = _reverse_index.get(name)
    if en_exact:
        for ex in exercises:
            if str(ex.get("name", "")).lower().strip() == en_exact:
                return ex

    # 3) поиск по ключевым словам по четырём полям базы сразу
    kws = search_keywords(name)
    if not kws:
        return None
    best, best_score = None, 0
    for ex in exercises:
        text = (
            str(ex.get("name", "")) + " "
            + str(ex.get("target", "")) + " "
            + str(ex.get("equipment", "")) + " "
            + str(ex.get("body_part", ex.get("category", "")))
        ).lower()
        score = sum(len(k) for k in kws if k in text)  # длинные ключи весят больше
        # бонус за совпадение целевой мышцы — важнее инвентаря
        tgt = str(ex.get("target", "")).lower()
        for k in kws:
            if k in tgt:
                score += 5
        if score > best_score:
            best, best_score = ex, score
    return best if best_score > 0 else None


def show_details(ru_name: str, show_media: bool = True):
    """Рисует гифку и русскую инструкцию. Вызывать ВНУТРИ открытого expander."""
    if not show_media:
        return

    info = find_exercise(ru_name)
    if info is None:
        st.session_state.setdefault("unmatched", set()).add(str(ru_name).strip())
        st.caption(f"«{ru_name}» не нашлось в базе — посмотри во вкладке «База упражнений».")
        return

    st.caption(
        f"{get_target_ru(info.get('target', ''))} · "
        f"{get_equipment_ru(info.get('equipment', ''))}"
    )

    gif_path = os.path.join(_DATASET_DIR, str(info.get("gif_url", "")))
    if gif_path and os.path.exists(gif_path):
        st.image(gif_path)  # гифка играет сама, без нажатий

    steps = _get_ru_steps(info)
    if steps:
        st.markdown("**Как выполнять:**")
        for i, step in enumerate(steps, 1):
            st.markdown(f"{i}. {step}")


def unmatched_report():
    """Список упражнений плана, которые не нашлись в базе."""
    missed = sorted(st.session_state.get("unmatched", set()))
    if not missed:
        return
    with st.expander(f"⚠️ Не найдено в базе: {len(missed)}"):
        st.write("Эти упражнения пока без гифки и описания:")
        st.code("\n".join(missed), language=None)
        st.caption("Скопируй список и пришли его — добавлю точный маппинг.")


def show():
    st.subheader("📚 База упражнений")
    exercises = load_exercises()
    st.caption(f"Всего упражнений: {len(exercises)}")

    query_raw = st.text_input(
        "Поиск (русский или английский)",
        placeholder="приседания, пресс, грудь, squat, press…",
    )
    kws = search_keywords(query_raw)
    if query_raw and not kws:
        st.info("Не понял запрос — попробуй: приседания, жим, тяга, пресс, плечи, ноги, бег.")

    parts = sorted({str(ex.get("body_part", ex.get("category", ""))) for ex in exercises})
    chosen_part = st.selectbox("Группа мышц", ["Все"] + [get_category_ru(p) for p in parts])

    filtered = []
    for ex in exercises:
        cat = str(ex.get("body_part", ex.get("category", "")))
        if chosen_part != "Все" and get_category_ru(cat) != chosen_part:
            continue
        if kws:
            text = (str(ex.get("name", "")) + " " + cat + " " + str(ex.get("target", ""))).lower()
            if not any(k in text for k in kws):
                continue
        filtered.append(ex)

    st.write(f"Найдено: {len(filtered)}")

    for ex in filtered[:50]:
        title = get_display_name(ex.get("name", "?"))
        cat = get_category_ru(ex.get("body_part", ex.get("category", "")))
        equip = get_equipment_ru(ex.get("equipment", ""))
        with st.expander(f"**{title}** — {cat} · {equip}"):
            gif_path = os.path.join(_DATASET_DIR, str(ex.get("gif_url", "")))
            if gif_path and os.path.exists(gif_path):
                st.image(gif_path)
            steps = _get_ru_steps(ex)
            if steps:
                st.markdown("**Как выполнять:**")
                for i, step in enumerate(steps, 1):
                    st.markdown(f"{i}. {step}")


if __name__ == "__main__":
    show()
