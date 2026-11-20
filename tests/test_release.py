# 1C-telemetry. Положительные и отрицательные проверки формата ZIP и BSL guard.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import io
import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_release import assemble
from check_sources import COPY, check_bsl
from release_common import safe_path
from verify_release import check_headers


class ReleaseTests(unittest.TestCase):
    """Проверяет реализацию упаковки и её независимый контроль."""

    def test_determinism_and_unicode(self):
        """Повторная сборка повторяет байты и сохраняет кириллическое имя."""
        files = {"Ext/Справка.txt": "данные\n".encode(), "VERSION": b"1.0.0-dev\n"}
        packet = assemble(files)
        self.assertEqual(packet, assemble(files))
        with zipfile.ZipFile(io.BytesIO(packet)) as archive:
            self.assertEqual(archive.namelist(), list(files))
            self.assertIsNone(archive.testzip())
            check_headers(packet, archive.infolist())

    def test_detect_corrupt_local_header(self):
        """Повреждение локального флага замечается независимо от центральной описи."""
        packet = assemble({"Модуль.bsl": b"x"})
        with zipfile.ZipFile(io.BytesIO(packet)) as archive:
            damaged = bytearray(packet)
            damaged[7] = 0
            with self.assertRaises(ValueError):
                check_headers(damaged, archive.infolist())

    def test_paths(self):
        """Отбрасывает переходы, разные разделители и неоднозначные пути."""
        for path in ("../file", "/file", "C:/file", "name\\other", "a//b", "./file"):
            self.assertFalse(safe_path(path), path)
        self.assertTrue(safe_path("CommonModules/ТЛМ/Ext/Module.bsl"))

    def test_bsl_guard(self):
        """BSL guard принимает документированный метод и отклоняет битые границы и токены."""
        good = f'// {COPY}\n// Образец.\nФункция Версия() Экспорт\n\tВозврат "x";\nКонецФункции\n// {COPY}\n'
        self.assertEqual(check_bsl(good, "fixture"), {"версия"})
        for code in (good.replace("КонецФункции", "КонецПроцедуры"),
                     good.replace('"x"', "\\")):
            with self.assertRaises(ValueError):
                check_bsl(code, "fixture")


if __name__ == "__main__":
    unittest.main()

# 1C-telemetry. Конец test_release.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
