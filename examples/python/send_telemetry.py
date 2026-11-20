# 1C-telemetry. Отправка исходных байтов средствами requests.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests


def send(mode, path):
    """Делает один HTTPS-запрос. Возвращает статус и ID подтверждённой записи."""
    base = urlsplit(os.environ["TLM_URL"])
    token = os.environ["TLM_TOKEN"]
    if (base.scheme != "https" or not base.hostname or base.username is not None
            or base.query or base.fragment or not re.fullmatch(r"[a-f0-9]{64}", token)):
        raise ValueError("Проверьте HTTPS URL и токен отправителя")
    url = base.geturl().rstrip("/") + "/" + mode
    options = {
        "headers": {"X-Token": token, "Accept": "application/json"},
        "allow_redirects": False,
        "verify": os.environ.get("TLM_PEM") or True,
        "timeout": 60,
    }
    if mode == "ping":
        response = requests.get(url, **options)
    else:
        if path is None:
            raise ValueError("Укажите исходный файл")
        if mode == "file":
            options["headers"]["Content-Type"] = "application/octet-stream"
            options["params"] = {"name": path.name}
            with path.open("rb") as payload:
                data = payload if path.stat().st_size else b""
                response = requests.post(url, data=data, **options)
        else:
            options["headers"]["Content-Type"] = "application/json; charset=utf-8"
            response = requests.post(url, data=path.read_bytes(), **options)

    status = response.status_code
    if 400 <= status < 500:
        raise ValueError(f"Запрос отклонён, HTTP {status}")
    if status != (200 if mode == "ping" else 201):
        raise ValueError(f"Запрос не подтверждён, HTTP {status}")
    try:
        body = response.json()
        message_id = body.get("id") if isinstance(body, dict) else None
    except ValueError:
        raise ValueError(f"Сервис вернул неожиданный ответ, HTTP {status}") from None
    valid_id = (message_id is None if mode == "ping" else isinstance(message_id, str)
                and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", message_id))
    if not isinstance(body, dict) or body.get("ok") is not True or not valid_id:
        raise ValueError(f"Сервис вернул неожиданный ответ, HTTP {status}")
    return status, message_id


def main():
    """Читает режим и путь из командной строки. Пример: send_telemetry.py file report.log."""
    parser = argparse.ArgumentParser(description="Передать JSON или файл в 1С")
    parser.add_argument("mode", choices=("ping", "json", "file"))
    parser.add_argument("path", type=Path, nargs="?")
    args = parser.parse_args()
    try:
        status, message_id = send(args.mode, args.path)
    except requests.RequestException:
        parser.exit(1, "HTTPS-запрос не подтверждён. Проверьте сеть, TLS и историю приёма.\n")
    except (KeyError, OSError):
        parser.exit(1, "Проверьте переменные TLM_URL, TLM_TOKEN, TLM_PEM и доступ к файлу.\n")
    except ValueError as error:
        parser.exit(1, f"{error}\n")
    print(status, message_id or "")


if __name__ == "__main__":
    sys.exit(main())

# 1C-telemetry. Конец send_telemetry.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
