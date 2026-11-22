import uuid
import urllib3

import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = {"User-Agent": "NexusFitness/1.0"}

# Читаем ключ из secrets.toml
path = r"C:\Users\honor\Documents\nexus\.streamlit\secrets.toml"
KEY = open(path, encoding="utf-8").read().split('"')[1]
print("Ключ прочитан, длина:", len(KEY))

# 1. Получаем токен
r = requests.post(
    "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
    headers={
        "Authorization": f"Basic {KEY}",
        "RqUID": str(uuid.uuid4()),
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        **UA,
    },
    data={"scope": "GIGACHAT_API_PERS"},
    verify=False,
    timeout=30,
)
print("OAuth:", r.status_code)
if r.status_code != 200:
    print(r.text[:500])
    raise SystemExit
token = r.json()["access_token"]

# 2. Спрашиваем список доступных моделей
r2 = requests.get(
    "https://api.giga.chat/v1/models",
    headers={"Authorization": f"Bearer {token}", **UA},
    verify=False,
    timeout=30,
)
print("Models:", r2.status_code)
print(r2.text[:1500])
