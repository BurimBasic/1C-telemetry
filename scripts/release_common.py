# 1C-telemetry. Чтение закреплённого дерева Git и хеширование файлов.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import hashlib
import re
import subprocess
from pathlib import PurePosixPath

COMPONENTS = {
    "client": "src/onec/client",
    "server": "src/onec/server",
    "examples": "examples",
}
FORMAT = "TLM_SOURCE_ZIP_RELEASE_MANIFEST_V1"


def git(*arguments):
    """Читает stdout Git как байты. Ошибка Git прекращает проверку."""
    return subprocess.check_output(["git", *arguments])


def blob_sha(data):
    """Вычисляет идентификатор Git blob для точных байтов файла."""
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def safe_path(path):
    """Разрешает только однозначные относительные пути ZIP."""
    name = PurePosixPath(path)
    return (
        path == name.as_posix() and not name.is_absolute() and name.parts
        and not any(part == ".." or ":" in part for part in name.parts)
        and not any(ch in path for ch in "\\\0")
    )


def frozen_tree(component, source):
    """Читает полный подкаталог точного коммита. Возвращает SHA деревьев и файлы."""
    if not re.fullmatch(r"[a-f0-9]{40}", source):
        raise ValueError("Укажите полный SOURCE_SHA")
    directory = COMPONENTS[component]
    if git("rev-parse", f"{source}^{{commit}}").strip().decode() != source:
        raise ValueError("SOURCE_SHA должен указывать на коммит")
    root = git("rev-parse", f"{source}^{{tree}}").strip().decode()
    subtree = git("rev-parse", f"{source}:{directory}").strip().decode()
    entries = git("ls-tree", "-rlz", subtree)
    files = {}
    portable_names = set()
    for raw in entries.rstrip(b"\0").split(b"\0"):
        info, path_bytes = raw.split(b"\t", 1)
        mode, kind, object_sha, size = info.decode().split()
        path = path_bytes.decode("utf-8", errors="strict")
        if kind != "blob" or mode not in {"100644", "100755"} or not safe_path(path):
            raise ValueError(f"Недопустимый объект в дереве: {path}")
        if path.casefold() in portable_names or path.lower().endswith((".zip", ".cfe", ".pem", ".key", ".pfx")):
            raise ValueError(f"Недопустимый путь для поставки: {path}")
        portable_names.add(path.casefold())
        data = git("cat-file", "blob", object_sha)
        if len(data) != int(size) or blob_sha(data) != object_sha:
            raise ValueError(f"Git blob не совпал: {path}")
        files[path] = data
    return root, subtree, dict(sorted(files.items()))


def inventory(files):
    """Строит опись путей, размеров и SHA-1 объектов Git для манифеста."""
    return [{"path": path, "size": len(data), "sha1": blob_sha(data)} for path, data in files.items()]


# 1C-telemetry. Конец release_common.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
