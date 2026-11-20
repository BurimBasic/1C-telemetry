# 1C-telemetry. Проверки исходников перед сборкой тестового ZIP.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from uuid import UUID

COPY = "Copyright © 2026 Тарасов Роман Олегович. Все права защищены."
MD = "{http://v8.1c.ru/8.3/MDClasses}"
CORE = "{http://v8.1c.ru/8.1/data/core}"
TYPES = {
    "client": {"Language", "Subsystem", "Role", "CommonModule", "Constant"},
    "server": {"Language", "Subsystem", "Role", "CommonModule", "HTTPService",
               "Constant", "Catalog", "InformationRegister"},
}
DIRECTORIES = {
    "Catalog": "Catalogs", "Constant": "Constants", "InformationRegister": "InformationRegisters",
    "CommonModule": "CommonModules", "HTTPService": "HTTPServices", "Role": "Roles",
    "Subsystem": "Subsystems", "Language": "Languages",
}
DECLARATION = re.compile(r"^\s*(?:Асинх\s+)?(Функция|Процедура)\s+(\w+)", re.IGNORECASE)
ENDING = re.compile(r"^\s*Конец(Функции|Процедуры)\b", re.IGNORECASE)


def require(check, path, message):
    """Останавливает сборку и показывает файл и нарушенное правило."""
    if not check:
        raise ValueError(f"{path}: {message}")


def check_bsl(source, path):
    """Проверяет границы методов, строки, комментарии и авторские блоки."""
    lines = source.lstrip("\ufeff").splitlines()
    require(COPY in "\n".join(lines[:5]) and COPY in "\n".join(lines[-5:]), path, "авторский блок")
    method = ""
    names = set()
    in_string = False
    for i, line in enumerate(lines):
        code = ""
        for token in re.finditer(r'""|"|//|.', line):
            item = token[0]
            if item == "//" and not in_string:
                break
            if item == '"':
                in_string = not in_string
            elif not in_string:
                code += item
        require("\\" not in code, path, f"обратная косая черта вне строки, строка {i + 1}")
        if match := DECLARATION.match(code):
            require(not method and i > 0 and lines[i - 1].startswith("//"), path,
                    f"метод без комментария или вложенное объявление, строка {i + 1}")
            method, name = match[1].casefold(), match[2].casefold()
            require(name not in names, path, f"дублируется метод {name}")
            names.add(name)
        elif match := ENDING.match(code):
            require(method == {"функции":"функция", "процедуры":"процедура"}[match[1].casefold()], path,
                    f"ошибка границы метода, строка {i + 1}")
            method = ""
    require(not method and not in_string and names, path, "незакрытая строка/метод или пустой модуль")
    return names


def check_copyright(properties, path):
    """Проверяет LocalStringType, которое Конфигуратор ожидает в Copyright."""
    copyright = properties.find(MD + "Copyright")
    path_to_russian = CORE + "item"
    require(copyright is not None and not (copyright.text or "").strip()
            and len(copyright) == 1, path, "Copyright должен быть LocalStringType")
    item = copyright.find(path_to_russian)
    require(item is not None and item.findtext(CORE + "lang") == "ru"
            and item.findtext(CORE + "content") == COPY,
            path, "Copyright должен содержать русский текст авторства")


def check_compatibility(properties, root):
    """Проверяет контролируемые свойства для целевого профиля 1С."""
    require(properties.findtext(MD + "DefaultLanguage") == "Language.Русский"
            and properties.findtext(MD + "InterfaceCompatibilityMode") == "TaxiEnableVersion8_2",
            root, "неверный основной язык или режим совместимости интерфейса")
    language = root / "Languages/Русский.xml"
    meta = ET.parse(language).getroot()[0].find(MD + "Properties")
    require(meta.findtext(MD + "ObjectBelonging") == "Adopted"
            and meta.findtext(MD + "LanguageCode") == "ru"
            and meta.findtext(MD + "ExtendedConfigurationObject") == "db4a9ccb-9ef5-4b3c-8577-b6fe5db1b62e",
            language, "основной язык должен быть заимствован с идентификатором базового русского языка")


def check_string_lengths(metadata, path):
    """Отбрасывает длинные ограниченные строки до обновления структуры базы."""
    for qualifiers in metadata.iter(CORE + "StringQualifiers"):
        length = qualifiers.findtext(CORE + "Length", "")
        require(length.isdecimal() and int(length) <= 1024, path,
                f"недопустимая ограниченная длина строки: {length!r}. Используйте 0 для неограниченной")


def check_extension(root, component):
    """Сверяет версии, состав XML, UUID, роли, маршруты, модули и штатную справку."""
    conf = ET.parse(root / "Configuration.xml").getroot()[0]
    properties = conf.find(MD + "Properties")
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    build = json.loads((root / "BUILD_STATUS.json").read_bytes())
    require(version == properties.findtext(MD + "Version") == build["extension_version"]
            and build["component"] == component, root, "расхождение версий")
    check_copyright(properties, root / "Configuration.xml")
    check_compatibility(properties, root)
    require(COPY in properties.findtext(MD + "Comment"), root, "авторство в Comment")
    require(properties.findtext(MD + "ConfigurationExtensionPurpose") == "AddOn"
            and properties.findtext(MD + "NamePrefix") == "ТЛМ_", root, "назначение или префикс")
    modules = {}
    ids = set()
    objects = {}
    paths = {"Configuration." + properties.findtext(MD + "Name"): root / "Configuration.xml"}
    for child in conf.find(MD + "ChildObjects"):
        kind, object_name = child.tag.removeprefix(MD), child.text
        standard_language = kind == "Language" and object_name == "Русский"
        require(kind in TYPES[component] and (standard_language or object_name.startswith("ТЛМ_")),
                root, f"лишний объект {object_name}")
        name = f"{kind}.{object_name}"
        xml = root / DIRECTORIES[kind] / f"{object_name}.xml"
        paths[name] = xml
        obj = ET.parse(xml).getroot()[0]
        check_string_lengths(obj, xml)
        objects[name] = obj
        require(obj.findtext(f"{MD}Properties/{MD}Name") == object_name and obj.tag == MD + kind,
                xml, "имя или тип не совпадает")
        for item in obj.iter():
            require(standard_language or item.tag != MD + "ExtendedConfigurationObject", xml, "заимствованный объект")
            if "uuid" in item.attrib:
                identity = UUID(item.attrib["uuid"])
                require(identity not in ids, xml, "неуникальный UUID")
                ids.add(identity)
        folder = xml.with_suffix("") / "Ext"
        if kind in {"CommonModule", "HTTPService"}:
            script = folder / "Module.bsl"
            source = script.read_text(encoding="utf-8-sig")
            modules[name] = check_bsl(source, script)
            paths[name + ".Module"] = script
            if kind == "CommonModule":
                require(f'Возврат "{version}";' in source, script, "Версия() расходится с VERSION")
                require(all(obj.findtext(f"{MD}Properties/{MD}{setting}") == expected
                            for setting, expected in {"Global":"false", "Privileged":"false",
                                                      "Server":"true", "ServerCall":"false"}.items()),
                        xml, "неверный контекст общего модуля")
        if kind == "Catalog":
            script = folder / "ObjectModule.bsl"
            modules[name] = check_bsl(script.read_text(encoding="utf-8-sig"), script)
            require("передзаписью" in modules[name], script, "нет проверки токена при записи")
            paths[name + ".ObjectModule"] = script
        if kind == "Subsystem":
            help_xml = folder / "Help.xml"
            require(ET.parse(help_xml).getroot()[0].text == "ru", help_xml, "нет страницы справки")
            require("v8help://" in (folder / "Help/ru.html").read_text(encoding="utf-8"), help_xml,
                    "нет штатного оформления справки")
        if kind == "Role":
            rights_xml = folder / "Rights.xml"
            paths[name + ".Rights"] = rights_xml
            for item in ET.parse(rights_xml).getroot():
                if item.tag.endswith("}object"):
                    target = item[0].text
                    require(target.split(".")[1].startswith("ТЛМ_"), rights_xml, "права вне расширения")
    require(TYPES[component] == {name.split(".")[0] for name in objects}, root, "неполный состав метаданных")
    if component == "server":
        name = "HTTPService.ТЛМ_ПриемДанных"
        service = objects[name]
        require(service.findtext(f"{MD}Properties/{MD}RootURL") == "telemetry", root, "неверный RootURL")
        routes = set()
        for template in service.findall(f"{MD}ChildObjects/{MD}URLTemplate"):
            route = template.findtext(f"{MD}Properties/{MD}Template")
            for method in template.findall(f"{MD}ChildObjects/{MD}Method/{MD}Properties"):
                handler = method.findtext(MD + "Handler").casefold()
                require(handler in modules[name], root, f"отсутствует обработчик {handler}")
                routes.add((route, method.findtext(MD + "HTTPMethod")))
        require(routes == {("/json", "POST"), ("/file", "POST"), ("/ping", "GET")}, root, "маршруты расходятся")
    index = ET.parse(root / "ConfigDumpInfo.xml").getroot()
    records = {item.attrib["name"]: item for item in index[0]}
    require(set(records) == set(paths), root, "состав ConfigDumpInfo расходится")
    for name, path in paths.items():
        require(records[name].attrib["configVersion"] == hashlib.sha1(path.read_bytes()).hexdigest(),
                path, "инвентарь ConfigDumpInfo устарел")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        require(not any(part in {"Forms", "ScheduledJobs", "DataProcessors", "Reports"} for part in path.parts),
                path, "лишний объект")
        if path.suffix in {".xml", ".bsl", ".html"}:
            source = path.read_text(encoding="utf-8-sig")
            require(COPY in source, path, "пропущено авторство")
            require(not re.search(r"(?i)(-----BEGIN [A-Z ]*PRIVATE KEY|[a-f0-9]{64})", source),
                    path, "обнаружен возможный открытый секрет")
            if path.suffix == ".xml":
                ET.fromstring(source)
    print(f"SOURCE_CHECK PASS {component} {len(objects)} объектов, {len(modules)} модулей")


if __name__ == "__main__":
    for target in sys.argv[1:] or TYPES:
        check_extension(Path("src/onec") / target, target)
    if len(sys.argv) == 1:
        example = Path("examples/schedule/Configuration.xml")
        props = ET.parse(example).getroot()[0].find(MD + "Properties")
        check_copyright(props, example)
        check_compatibility(props, example.parent)

# 1C-telemetry. Конец check_sources.py.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
