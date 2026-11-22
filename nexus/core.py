"""Nexus Fitness — ядро: расчёты и генерация планов."""

import random
from dataclasses import dataclass, field

MALE = "мужской"
FEMALE = "женский"
GOALS = ["Похудение", "Поддержание формы", "Набор массы"]
LEVELS = ["Новичок", "Средний", "Продвинутый"]
EQUIPMENT = ["Без инвентаря", "Гантели", "Полный зал"]


@dataclass
class Profile:
    name: str = ""
    sex: str = MALE
    age: int = 25
    height: int = 175
    weight: float = 75.0
    goal: str = GOALS[1]
    level: str = LEVELS[0]
    days_per_week: int = 3
    equipment: str = EQUIPMENT[0]
    weight_history: list = field(default_factory=list)  # [(дд.мм.гггг, кг)]


def bmi(p: Profile) -> float:
    return p.weight / (p.height / 100) ** 2


def bmi_category(v: float) -> str:
    if v < 18.5:
        return "Недостаточный вес"
    if v < 25:
        return "Норма"
    if v < 30:
        return "Избыточный вес"
    return "Ожирение"


def calories(p: Profile) -> int:
    """Миффлин–Сан Жеор + активность + поправка на цель."""
    base = 10 * p.weight + 6.25 * p.height - 5 * p.age
    bmr = base + (5 if p.sex == MALE else -161)
    tdee = bmr * 1.45  # умеренная активность
    if p.goal == "Похудение":
        tdee *= 0.8
    elif p.goal == "Набор массы":
        tdee *= 1.15
    return int(tdee // 10 * 10)


def macros(p: Profile, kcal: int) -> dict:
    if p.goal == "Набор массы":
        protein, fat = 0.25, 0.28
    elif p.goal == "Похудение":
        protein, fat = 0.30, 0.27
    else:
        protein, fat = 0.25, 0.30
    return {
        "белки": int(kcal * protein / 4),
        "жиры": int(kcal * fat / 9),
        "углеводы": int(kcal * (1 - protein - fat) / 4),
    }


# --- Библиотека упражнений ---
# (название, группы мышц, инвентарь: 0 — без, 1 — гантели, 2 — зал)
EXERCISES = [
    ("Отжимания", ["грудь", "руки"], 0),
    ("Планка", ["пресс"], 0),
    ("Приседания без веса", ["ноги"], 0),
    ("Выпады", ["ноги"], 0),
    ("Бёрпи", ["всё тело"], 0),
    ("Скручивания", ["пресс"], 0),
    ("Супермен", ["спина"], 0),
    ("Обратные отжимания", ["руки"], 0),
    ("Жим гантелей стоя", ["руки", "плечи"], 1),
    ("Тяга гантели в наклоне", ["спина"], 1),
    ("Жим гантелей лёжа", ["грудь"], 1),
    ("Приседания с гантелями", ["ноги"], 1),
    ("Махи гантелями", ["плечи"], 1),
    ("Тяга гантелей в наклоне", ["спина"], 1),
    ("Приседания со штангой", ["ноги"], 2),
    ("Жим штанги лёжа", ["грудь"], 2),
    ("Становая тяга", ["спина"], 2),
    ("Подтягивания", ["спина", "руки"], 2),
    ("Жим штанги стоя", ["плечи", "руки"], 2),
    ("Тяга верхнего блока", ["спина"], 2),
]

SPLITS = {2: ["Всё тело A", "Всё тело B"],
          3: ["Всё тело A", "Всё тело B", "Всё тело C"],
          4: ["Грудь + Руки", "Ноги", "Спина + Плечи", "Всё тело D"],
          5: ["Грудь + Руки", "Ноги", "Спина + Плечи", "Пресс + Кор", "Всё тело E"]}

TARGET = {  # группы мышц на каждый день по количеству тренировок
    2: [["всё тело", "грудь", "спина", "ноги"], ["всё тело", "руки", "пресс", "плечи"]],
    3: [["грудь", "спина", "ноги"], ["руки", "плечи", "пресс"], ["всё тело", "ноги", "спина"]],
    4: [["грудь", "руки"], ["ноги"], ["спина", "плечи"], ["всё тело", "пресс"]],
    5: [["грудь", "руки"], ["ноги"], ["спина", "плечи"], ["пресс"], ["всё тело", "ноги"]],
}

N_EX = {"Новичок": 5, "Средний": 6, "Продвинутый": 7}

SCHEMES = {"Похудение": (3, "12–15", 45), "Поддержание формы": (3, "10–12", 60),
           "Набор массы": (4, "8–10", 90)}


def _allowed(equip: str) -> int:
    return {"Без инвентаря": 0, "Гантели": 1, "Полный зал": 2}[equip]


def weekly_plan(p: Profile) -> dict:
    """Детерминированный недельный план (seed по профилю)."""
    rng = random.Random(f"{p.sex}{p.age}{p.goal}{p.level}{p.equipment}{p.days_per_week}")
    days = min(p.days_per_week, 5)
    max_equip = _allowed(p.equipment)
    sets, reps, rest = SCHEMES[p.goal]
    plan = {}
    for i, day_name in enumerate(SPLITS[days][:days]):
        targets = TARGET[days][i]
        pool = [ex for ex in EXERCISES if ex[2] <= max_equip and any(g in ex[1] for g in targets)]
        rng.shuffle(pool)
        picked, seen = [], set()
        for ex in pool:
            if len(picked) >= N_EX[p.level]:
                break
            if ex[0] not in seen:
                picked.append(ex)
                seen.add(ex[0])
        # немного пресса/кора в каждый день для баланса
        if "пресс" not in targets:
            core_pool = [ex for ex in EXERCISES
                         if ex[2] <= max_equip and "пресс" in ex[1] and ex[0] not in seen]
            if core_pool:
                picked.append(rng.choice(core_pool))
                seen.add(picked[-1][0])
        plan[day_name] = [{"name": ex[0], "sets": sets, "reps": reps,
                           "rest": f"{rest} сек"} for ex in picked]
    return plan


MEALS = {
    "Завтрак": [("Овсянка с ягодами и орехами", 450), ("Омлет из 3 яиц с овощами", 350),
                ("Творог с мёдом и бананом", 400), ("Гречка с яйцом и тунцом", 480)],
    "Обед": [("Куриная грудка с рисом и овощами", 650), ("Паста с индейкой", 600),
             ("Говядина с гречкой и салатом", 700), ("Рыба с картофелем", 620)],
    "Ужин": [("Запечённая рыба с овощами", 450), ("Тушёная курица с булгуром", 500),
             ("Омлет с овощами и сыром", 400), ("Салат с тунцом и яйцом", 380)],
    "Перекусы": [("Греческий йогурт", 150), ("Горсть орехов", 180),
                 ("Яблоко + сыр", 160), ("Протеиновый батончик", 200)],
}


def meal_plan(p: Profile) -> dict:
    kcal = calories(p)
    rng = random.Random(f"{p.name}meal{kcal}")
    slots = {"Завтрак": 0.27, "Обед": 0.36, "Ужин": 0.27, "Перекусы": 0.10}
    result = {}
    for meal, share in slots.items():
        dish = rng.choice(MEALS[meal])
        k = max(1, round(kcal * share / dish[1]))
        result[meal] = f"{dish[0]} — {k} порц. (~{kcal * share:.0f} ккал)"
    return result
