# 1C-telemetry. Проверяет Python и cURL на синтетическом локальном HTTPS-обработчике.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import importlib.util
import json
import os
import secrets
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/python/send_telemetry.py"


class Fixture(BaseHTTPRequestHandler):
    """Имитирует только конверты ответа API. Сохраняет полученные байты в памяти."""

    def do_POST(self):
        """Проверяет такой же контракт, как при GET, и читает присланное тело."""
        self.do_GET()

    def do_GET(self):
        """Возвращает ping, ID приёма, редирект или заведомо неверное тело."""
        target = urlsplit(self.path)
        received = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.received.append((self.command, target.path, parse_qs(target.query),
                                     self.headers.get("X-Token"), received))
        body = dict(ok=True)
        status = 200
        if target.path.startswith("/redirect/"):
            self.send_response(302)
            self.send_header("Location", "/central/ping")
            self.end_headers()
            return
        if target.path.startswith("/bad/"):
            body = dict(ok="true")
        elif target.path.endswith(("/file", "/json")):
            status = 201
            body["id"] = str(uuid4())
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        """Не выводит в тестовый лог содержимое заголовков или запросов."""


@unittest.skipUnless(shutil.which("openssl"), "Для локального TLS fixture нужен openssl")
class ExampleTests(unittest.TestCase):
    """Проверяет отправку исходных байтов и отказы TLS/прикладного протокола."""

    @classmethod
    def setUpClass(cls):
        """Запускает свой HTTPS-сервер на 127.0.0.1 со случайным временным сертификатом."""
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        cls.directory = Path(temp.name)
        cls.pem = cls.directory / "local.pem"
        key = cls.directory / "local.key"
        subprocess.run(["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
                        "-days", "1", "-subj", "/CN=telemetry-test",
                        "-addext", "subjectAltName=IP:127.0.0.1",
                        "-keyout", str(key), "-out", str(cls.pem)],
                       check=True, capture_output=True)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
        cls.server.received = []
        tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        tls.load_cert_chain(cls.pem, key)
        cls.server.socket = tls.wrap_socket(cls.server.socket, server_side=True)
        thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        thread.start()
        cls.addClassCleanup(cls.server.server_close)
        cls.addClassCleanup(cls.server.shutdown)
        cls.base = f"https://127.0.0.1:{cls.server.server_port}"
        cls.token = secrets.token_hex(32)

    def python(self, prefix, mode, path=None, *, trust=True, base=None, token=None):
        """Запускает настоящий скрипт Python с тестовым токеном и TEMP PEM."""
        environment = {**os.environ, "TLM_URL": (base or self.base) + prefix,
                       "TLM_TOKEN": self.token if token is None else token, "TLM_PEM": str(self.pem) if trust else ""}
        command = [sys.executable, str(EXAMPLE), mode]
        if path:
            command.append(str(path))
        return subprocess.run(command, env=environment, text=True, capture_output=True, timeout=10)

    @unittest.skipUnless(importlib.util.find_spec("requests"), "Для примера Python нужен requests")
    def test_python_bodies(self):
        """Проверяет ping, непрозрачный JSON, двоичный и пустой файлы с кириллицей."""
        result = self.python("/central", "ping")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "200"), result.stderr)
        items = [("json", "report.json", '  {"тест": [1,2]}\r\n'.encode()),
                 ("file", "Отчёт + 1.bin", b"\x00\xff\r\n"), ("file", "Пустой.bin", b"")]
        for mode, name, data in items:
            path = self.directory / name
            path.write_bytes(data)
            result = self.python("/central/", mode, path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith("201 "))
            expected_names = {"name": [name]} if mode == "file" else {}
            self.assertEqual(self.server.received[-1], ("POST", "/central/" + mode, expected_names, self.token, data))

    @unittest.skipUnless(importlib.util.find_spec("requests"), "Для примера Python нужен requests")
    def test_python_literal_and_encoded_tokens(self):
        """Проверяет 123, один символ, Unicode, концевые пробелы и длинный заголовок."""
        for token, header in (("123", "123"), ("x", "x"),
                              (" А %+~!*() ", "%20%D0%90%20%25%2B~%21%2A%28%29%20"),
                              ("я" * 256, "%D1%8F" * 256), (" ", "%20")):
            with self.subTest(header=header[:32]):
                result = self.python("/central", "ping", token=token)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.server.received[-1][3], header)

    @unittest.skipUnless(importlib.util.find_spec("requests"), "Для примера Python нужен requests")
    def test_python_rejects_redirect_and_bad_ok(self):
        """Редирект не отправляет токен по другому адресу. Строка ok не считается успехом."""
        for prefix in ("/redirect", "/bad"):
            count = len(self.server.received)
            result = self.python(prefix, "ping")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(len(self.server.received), count + 1)
            self.assertNotIn(self.token, result.stderr)

    @unittest.skipUnless(importlib.util.find_spec("requests"), "Для примера Python нужен requests")
    def test_python_rejects_untrusted_and_wrong_san(self):
        """Неотмеченный доверенный сертификат или неверный SAN не передаёт HTTP-запрос."""
        count = len(self.server.received)
        self.assertNotEqual(self.python("/central", "ping", trust=False).returncode, 0)
        self.assertNotEqual(self.python("/central", "ping", base=self.base.replace("127.0.0.1", "localhost")).returncode, 0)
        self.assertEqual(len(self.server.received), count)

    @unittest.skipUnless(shutil.which("curl"), "Для теста примера нужен curl")
    def test_curl_binary_post(self):
        """cURL передаёт файл с --data-binary и подтверждает UUID из JSON."""
        name = "Отчёт + cURL.bin"
        path = self.directory / name
        data = bytes(range(256))
        path.write_bytes(data)
        route = "/central/file"
        command = ["curl", "-q", "--silent", "--show-error", "--fail-with-body", "--proto", "=https",
                   "--cacert", str(self.pem), "--max-time", "10", "--write-out", "\n%{http_code}",
                   "-H", "X-Token: " + self.token, "-H", "Content-Type: application/octet-stream",
                   "--data-binary", "@" + str(path)]
        from urllib.parse import quote
        result = subprocess.run(command + [self.base + route + "?name=" + quote(name)],
                                check=True, capture_output=True, text=True)
        body, status = result.stdout.rsplit("\n", 1)
        self.assertEqual(status, "201")
        self.assertIs(json.loads(body).get("ok"), True)
        self.assertEqual(self.server.received[-1], ("POST", route, {"name": [name]}, self.token, data))


if __name__ == "__main__":
    unittest.main()

# 1C-telemetry. Конец test_examples.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
