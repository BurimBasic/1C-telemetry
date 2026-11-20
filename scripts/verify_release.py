# 1C-telemetry. Независимое чтение ZIP и сравнение с зафиксированным деревом Git.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import argparse
import hashlib
import io
import json
import struct
import zipfile
from pathlib import Path

from release_common import FORMAT, blob_sha, frozen_tree, inventory, safe_path


def require(condition, reason):
    """Прерывает проверку с причиной, если условие не выполнено."""
    if not condition:
        raise ValueError(reason)


def check_headers(data, entries):
    """Проверяет EOCD, центральные и локальные заголовки, флаги и размеры ZIP32."""
    signature, disk, start_disk, disk_count, count, length, offset, comment = struct.unpack_from(
        "<4s4H2IH", data, len(data) - 22,
    )
    require(signature == b"PK\x05\x06" and disk == start_disk == comment == 0
            and disk_count == count == len(entries) < 65535 and offset + length == len(data) - 22,
            "Неверный завершающий заголовок ZIP32")
    cursor = offset
    file_end = 0
    for entry in entries:
        central = struct.unpack_from("<4s6H3I5H2I", data, cursor)
        local = struct.unpack_from("<4s5H3I2H", data, entry.header_offset)
        name = entry.filename.encode("utf-8")
        flags = 0 if name.isascii() else 0x0800
        require(central[0] == b"PK\x01\x02" and local[0] == b"PK\x03\x04", "Неверная сигнатура")
        require(central[2:5] == (20, flags, 8) and local[1:4] == (20, flags, 8),
                f"Метод или флаги: {entry.filename}")
        require(central[7:14] == (entry.CRC, entry.compress_size, entry.file_size, len(name), 0, 0, 0)
                and local[6:] == (entry.CRC, entry.compress_size, entry.file_size, len(name), 0),
                f"Размер, CRC или служебные поля: {entry.filename}")
        require(central[16] == entry.header_offset == file_end and
                data[cursor + 46:cursor + 46 + len(name)] == name and
                data[file_end + 30:file_end + 30 + len(name)] == name,
                f"Имя или расположение записи: {entry.filename}")
        file_end += 30 + len(name) + entry.compress_size
        cursor += 46 + len(name)
    require(cursor == offset + length and file_end == offset, "Заголовки содержат лишние данные")


def verify(path):
    """Проверяет ZIP, манифест, отдельный SHA-256 и все байты Git blob."""
    data = path.read_bytes()
    manifest = json.loads(path.with_suffix(".zip.manifest.json").read_bytes())
    digest = hashlib.sha256(data).hexdigest()
    root, subtree, files = frozen_tree(manifest["component"], manifest["source_commit"])
    require(manifest["format"] == FORMAT and manifest["status"] == "TEST"
            and manifest["source_commit_tree"] == root and manifest["source_subtree"] == subtree
            and manifest["source_files"] == len(files) and manifest["files"] == inventory(files),
            "Манифест не совпадает с деревом Git")
    require(manifest["zip_path"] == f"artifacts/releases/{path.name}" and manifest["zip_size"] == len(data)
            and manifest["sha256"] == digest and manifest["git_blob_sha1"] == blob_sha(data)
            and path.with_suffix(".zip.sha256").read_text().strip() == f"{digest}  {path.name}",
            "Контрольная сумма опубликованных байтов не совпала")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = archive.namelist()
        require(names == list(files) and len(names) == len(set(names)) and all(map(safe_path, names)),
                "Список файлов не совпадает с деревом Git")
        require(all(archive.read(name) == payload for name, payload in files.items()) and archive.testzip() is None,
                "Путь, содержимое или CRC файла не совпали")
        check_headers(data, entries)
    counts = manifest["archive"]
    require(counts["file_count"] == len(files) and counts["entry_count"] == len(entries)
            and counts["zip32"] is True and counts["method"] == 8, "Поля формата ZIP в манифесте")
    print(f"ZIP_ROUNDTRIP PASS {len(files)} файлов, {len(entries)} записей, {digest}")


def main():
    """Проверяет каждый ZIP и два соседних файла подтверждения."""
    parser = argparse.ArgumentParser(description="Проверить ZIP и сравнить с исходным деревом Git")
    parser.add_argument("archives", nargs="+", type=Path)
    for path in parser.parse_args().archives:
        verify(path)


if __name__ == "__main__":
    main()

# 1C-telemetry. Конец verify_release.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
