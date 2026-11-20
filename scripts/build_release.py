# 1C-telemetry. Воспроизводимая упаковка исходных деревьев клиента, сервера и примеров.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

from release_common import COMPONENTS, FORMAT, blob_sha, frozen_tree, inventory


def assemble(files):
    """Пакует отсортированные файлы как ZIP32. Дата и метаданные фиксированы."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, allowZip64=False) as archive:
        for name, data in files.items():
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buffer.getvalue()


def build(component, source, revision, output, evidence, version):
    """Сохраняет ZIP, SHA-256 и манифест. Прежние байты защищены от замены."""
    root, subtree, files = frozen_tree(component, source)
    if component != "examples":
        version = files["VERSION"].decode().strip()
        if json.loads(files["BUILD_STATUS.json"])["extension_version"] != version:
            raise ValueError("Версия расширения расходится с BUILD_STATUS.json")
        if "Configuration.xml" not in files:
            raise ValueError("Configuration.xml должен находиться в корне")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-dev)?", version or ""):
        raise ValueError("Укажите версию комплекта")
    stem = f"1C-telemetry_{component}_{version}"
    name = stem + (f"-r{revision}" if component != "examples" else "") + ".zip"
    data = assemble(files)
    digest = hashlib.sha256(data).hexdigest()
    members = inventory(files)
    manifest = {
        "format": FORMAT, "component": component, "extension_version": version,
        "revision": revision, "status": "TEST",
        "source_commit": source, "source_commit_tree": root, "source_subtree": subtree,
        "source_files": len(members), "files": members, "zip_path": f"artifacts/releases/{name}",
        "zip_size": len(data), "sha256": digest, "git_blob_sha1": blob_sha(data),
        "archive": {"method": 8, "bit11": "all non-ASCII names", "zip32": True,
                    "file_count": len(members), "entry_count": len(members)},
        "testing": evidence,
        "limitations": [
            "TEST. Результаты установки и CheckConfig приведены в отчёте приёмки.",
            "Передача 2–3 ГиБ зависит от платформы и публикации. Подтверждённого предела пока нет.",
        ],
    }
    artifacts = {
        name: data,
        name + ".sha256": f"{digest}  {name}\n".encode(),
        name + ".manifest.json": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode(),
    }
    for filename, content in artifacts.items():
        path = output / filename
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"Имя уже занято другими байтами: {path}")
    output.mkdir(parents=True, exist_ok=True)
    for filename, content in artifacts.items():
        (output / filename).write_bytes(content)
    print(f"{name} {len(data)} байт {digest}")


def main():
    """Принимает точный SHA, версию примеров и результаты проверок."""
    parser = argparse.ArgumentParser(description="Собрать исходный TEST ZIP из точного Git SHA")
    parser.add_argument("component", choices=COMPONENTS)
    parser.add_argument("source")
    parser.add_argument("--version")
    parser.add_argument("--revision", type=int, default=1, choices=range(1, 100))
    parser.add_argument("--output", type=Path, default=Path("artifacts/releases"))
    parser.add_argument("--evidence", type=Path, required=True)
    options = parser.parse_args()
    evidence = json.loads(options.evidence.read_text(encoding="utf-8"))
    if any(item.get("source_commit") != options.source for item in evidence):
        raise ValueError("Результаты проверок должны относиться к SOURCE_SHA")
    build(options.component, options.source, options.revision, options.output, evidence, options.version)


if __name__ == "__main__":
    main()

# 1C-telemetry. Конец build_release.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
