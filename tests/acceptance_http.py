# 1C-telemetry. Синтетические HTTPS-запросы для тестовой публикации.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import argparse
import hashlib
import json
import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests


def request(url, token, method, route, expected, *, payload=None, media=None, name=None, error=None):
    """Проверяет HTTP и прикладной ответ. Возвращает безопасное подтверждение без URL и токена."""
    headers = {}
    if token:
        headers["X-Token"] = quote(token, safe="")
    if media:
        headers["Content-Type"] = media
    started = time.monotonic()
    response = requests.request(method, url + route, headers=headers, data=payload,
                                params={"name": name} if name is not None else None,
                                verify=os.environ.get("TLM_PEM") or True, allow_redirects=False,
                                timeout=int(os.environ.get("TLM_TIMEOUT", "60")))
    if response.status_code != expected:
        raise ValueError(f"{route}: ожидается HTTP {expected}, получен {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        raise ValueError(f"{route}: ожидается JSON API, HTTP {expected}") from None
    if not isinstance(body, dict) or body.get("ok") is not (expected < 300):
        raise ValueError(f"{route}: неверное подтверждение операции")
    identifier = body.get("id")
    if expected == 201 and not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", identifier or ""):
        raise ValueError(f"{route}: неверный идентификатор")
    if expected != 201 and identifier is not None or error is not None and body.get("error") != error:
        raise ValueError(f"{route}: неверный ответ")
    return dict(http=expected, id=identifier, seconds=round(time.monotonic() - started, 3))


def smoke(url, first, second, run_id):
    """Сохраняет синтетические записи двумя токенами. Для каждой выдаёт ID или ожидаемый отказ."""
    check = lambda token, method, route, status, **kw: request(url, token, method, route, status, **kw)
    yield dict(case="ping", **check(first, "GET", "ping", 200))
    yield dict(case="anonymous", **check(None, "GET", "ping", 401, error="invalid_token"))
    yield dict(case="invalid-token", **check(secrets.token_hex(32), "GET", "ping", 401, error="invalid_token"))
    json_type = "application/json; charset=utf-8"
    file_type = "application/octet-stream"
    payload = ('{\r\n  "проверка": "' + run_id + '",\r\n  "значения": [true, {"байты": 2}]\r\n}\r\n').encode()
    binary = b"\0\xff" + run_id.encode() + b"\r\n"
    filename = f"Отчёт + {run_id}.bin"
    jobs = [
        (first, "json", payload, json_type, None, "first"),
        (second, "json", payload, json_type, None, "second"),
        (first, "json", payload, json_type, None, "first"),
        (first, "file", binary, file_type, filename, "first"),
        (second, "file", binary, file_type, filename, "second"),
        (first, "file", b"", file_type, f"Пустой {run_id}.txt", "first"),
    ]
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(check, token, "POST", route, 201, payload=data, media=media, name=name)
                   for token, route, data, media, name, _ in jobs]
        ids = set()
        for job, future in zip(jobs, futures, strict=True):
            _, route, data, _media, name, sender = job
            result = future.result()
            if result["id"] in ids:
                raise ValueError("Сервис повторил идентификатор записи")
            ids.add(result["id"])
            yield dict(case=route, sender=sender, name=name, size=len(data),
                       sha256=hashlib.sha256(data).hexdigest(), **result)
    yield dict(case="invalid-encoding", **check(first, "POST", "json", 400, payload=b"\xff",
                                               media=json_type, error="invalid_encoding"))
    yield dict(case="missing-name", **check(first, "POST", "file", 400, payload=b"\0",
                                           media=file_type, error="invalid_filename"))
    yield dict(case="wrong-media", **check(first, "POST", "json", 415, payload=b"{}",
                                          media="text/plain", error="unsupported_media_type"))


def supplied_file(url, token, path):
    """Измеряет доставку указанного файла одним POST, не создавая тестовый файл и не повторяя запрос."""
    size = path.stat().st_size
    with path.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
        handle.seek(0)
        receipt = request(url, token, "POST", "file", 201, payload=handle if size else b"",
                          media="application/octet-stream", name=path.name)
    return dict(case="supplied-file", name=path.name, size=size, sha256=digest, **receipt)


def main():
    """Запускает HTTPS-приёмку только по явно заданному адресу тестовой публикации."""
    parser = argparse.ArgumentParser(description="HTTPS-приёмка тестовой 1С (создаёт записи)")
    parser.add_argument("--file", type=Path, help="Вместо smoke передать один готовый файл")
    args = parser.parse_args()
    try:
        url = os.environ["TLM_URL"].rstrip("/") + "/"
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Проверьте TLM_URL")
        token = os.environ["TLM_TOKEN"]
        if args.file:
            print(json.dumps(supplied_file(url, token, args.file), ensure_ascii=False))
        else:
            second = os.environ["TLM_TOKEN_2"]
            if second == token:
                raise ValueError("Нужны два разных тестовых токена")
            run_id = "tlm-" + secrets.token_hex(8)
            print(json.dumps(dict(run_id=run_id), ensure_ascii=False))
            for result in smoke(url, token, second, run_id):
                print(json.dumps(result, ensure_ascii=False))
    except requests.RequestException:
        parser.exit(1, "Запрос не подтверждён. Проверьте сеть, TLS и историю приёма.\n")
    except (OSError, KeyError):
        parser.exit(1, "Проверьте локальный файл или настройки окружения.\n")
    except ValueError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()

# 1C-telemetry. Конец acceptance_http.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
