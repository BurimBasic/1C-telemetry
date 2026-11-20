# 1C-telemetry

Передаёт готовый JSON и файлы из локальных баз 1С и внешних скриптов в одну центральную базу по HTTPS. Сервер определяет отправителя по токену, сохраняет JSON в регистре, а файлы — в выделенном каталоге. Локальную базу отправителя публиковать не нужно.

**20.11.2026 · TEST 1.0.3-dev.** ZIP проверены побайтово. Язык и режим интерфейса согласованы с целевой базой. Установка и приёмка на 1С 8.3.27.2342 с Apache ожидаются. [Результаты проверок и ограничения](docs/ACCEPTANCE.md).

| Пакет для Конфигуратора | Скачать | Сверить |
|---|---|---|
| Сервер `ТЛМ_Сервер` | [ZIP](https://github.com/BurimBasic/1C-telemetry/raw/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_server_1.0.3-dev-r1.zip) | [SHA-256](https://github.com/BurimBasic/1C-telemetry/blob/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_server_1.0.3-dev-r1.zip.sha256) · [Манифест](https://github.com/BurimBasic/1C-telemetry/blob/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_server_1.0.3-dev-r1.zip.manifest.json) |
| Клиент `ТЛМ_Клиент` | [ZIP](https://github.com/BurimBasic/1C-telemetry/raw/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_client_1.0.3-dev-r1.zip) | [SHA-256](https://github.com/BurimBasic/1C-telemetry/blob/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_client_1.0.3-dev-r1.zip.sha256) · [Манифест](https://github.com/BurimBasic/1C-telemetry/blob/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_client_1.0.3-dev-r1.zip.manifest.json) |
| Примеры BSL, PowerShell, Python, cURL и штатного задания | [ZIP](https://github.com/BurimBasic/1C-telemetry/raw/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_examples_1.0.3-dev.zip) | [SHA-256](https://github.com/BurimBasic/1C-telemetry/blob/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_examples_1.0.3-dev.zip.sha256) · [Манифест](https://github.com/BurimBasic/1C-telemetry/blob/39caa306ebad13e0c85f5812a808afd767f19c12/artifacts/releases/1C-telemetry_examples_1.0.3-dev.zip.manifest.json) |

## Быстрый старт

1. В центральной базе загрузите серверный ZIP как дополнение, настройте каталог и HTTPS-публикацию. Создайте клиента в справочнике `ТЛМ_Клиенты`, введите собственный уникальный токен и включите приём. На стенде подойдёт `123`.
2. В базе-отправителе загрузите клиентский ZIP и задайте адрес сервиса и токен. Например, `https://server.example/central/hs/telemetry/`.
3. В своей серверной процедуре вызовите нужный метод. Для отправки по расписанию подключите своё штатное регламентное задание.

```bsl
Диагностика = ТЛМ_Клиент.ПроверитьПодключение();
Итог = ТЛМ_Клиент.ОтправитьJSON("{""результат"":""готово""}");
ИтогФайла = ТЛМ_Клиент.ОтправитьФайл(ПутьКФайлу);
```

| Внешние скрипты | Маршрут |
|---|---|
| Проверка связи | `GET ping` |
| Исходный текст UTF-8 | `POST json` |
| Двоичный файл | `POST file?name=backup.log` |

Во всех запросах нужен `X-Token`. Клиент 1С и примеры кодируют исходный токен по [правилам API](docs/API.md). Один файл передаётся одним POST. Допустимый размер зависит от 1С, веб-сервера и ресурсов. Передача 2–3 ГиБ ещё не проверена. При неизвестном результате передачи проверьте историю до повтора.

## Документация

- [Установка, настройка ролей и самоподписанный HTTPS](docs/INSTALLATION.md).
- [HTTP API](docs/API.md), [результаты BSL и ошибки](docs/TRANSFER-AND-ERRORS.md), [исполняемые примеры](examples/README.md).
- [План испытаний](docs/TEST-PLAN.md), [отчёт WAVE 001](docs/ACCEPTANCE.md), [история изменений](CHANGELOG.md).
- [Спецификация](docs/SPECIFICATION.md), [сборка ZIP](docs/RELEASE-RUNBOOK.md), [стандарты BSL](docs/CODE-DOCUMENTATION-STANDARD.md), [безопасность](SECURITY.md), [авторские права](COPYRIGHT.md).

Задачи [#1](https://github.com/BurimBasic/1C-telemetry/issues/1), [#2](https://github.com/BurimBasic/1C-telemetry/issues/2), [#3](https://github.com/BurimBasic/1C-telemetry/issues/3), [#4](https://github.com/BurimBasic/1C-telemetry/issues/4), [#5](https://github.com/BurimBasic/1C-telemetry/issues/5).

Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
