# HTTPS API v1 — проект контракта

Base URL задаётся администратором: https://host/publication/hs/telemetry/ . Допустим IP при соответствующем SAN. Без клиентских сертификатов, логина, OAuth и сессий. Единственный обязательный заголовок авторизации: X-Token: <секрет>. Токен определяет клиента на сервере; тело запроса не влияет на identity. Ответы JSON UTF-8. Маршруты не предоставляют чтение, удаление или выполнение полученных данных.

| Метод | Относительный URL | Тело | Успех |
|---|---|---|---|
| POST | json | исходная строка UTF-8, application/json | 201 |
| POST | file?name=backup.log | raw bytes, application/octet-stream; имя UTF-8 percent-encoded | 201 |
| GET | ping | нет | 200 |

Успешная запись: {"ok":true,"id":"<uuid>"}; ping: {"ok":true}. Ошибка: {"ok":false,"error":"<стабильный код>"}. Статус: 400 bad_request / invalid_encoding / invalid_filename, 401 invalid_token (включая заблокированный), 413 payload_too_large, 415 unsupported_media_type, 500 storage_error, 503 unavailable. Никаких токенов, стека, внутренних путей или данных другого клиента в ответе. На стороне веб-сервера возможен собственный HTTP-ответ, клиент обязан его обработать без предположения JSON. Успех только после сохранения. Неизвестный исход при сетевом сбое; повтор может создать новую запись. Нет обязательных idempotency key или предварительной регистрации загрузки.

## Компактные примеры (будущий API, не проверены на работающем сервисе)
PowerShell (имя ASCII в примере; доверие к сертификату настроено в Windows):
    $h = @{'X-Token'=$env:TLM_TOKEN}
    Invoke-RestMethod "$env:TLM_URL/json" -Method Post -Headers $h -ContentType 'application/json; charset=utf-8' -Body '{"backup":"OK"}'
    Invoke-RestMethod "$env:TLM_URL/file?name=backup.log" -Method Post -Headers $h -ContentType 'application/octet-stream' -InFile 'C:\Backup\backup.log'

Python (requests, проверенный публичный PEM при частном сертификате; для системного/публичного доверия убрать verify):
    import os, requests
    r = requests.post(os.environ["TLM_URL"]+"/json", headers={"X-Token":os.environ["TLM_TOKEN"]}, data=b'{"backup":"OK"}', verify="server.pem", timeout=60)
    r.raise_for_status()
Для файла использовать открытый в режиме rb файл как data, params={"name":"backup.log"}, заголовок Content-Type application/octet-stream; raise_for_status().

cURL (curl.exe в Windows PowerShell):
    curl --fail-with-body --cacert server.pem -H "X-Token: TOKEN" -H "Content-Type: application/json" --data-binary @report.json https://host/publication/hs/telemetry/json
    curl --fail-with-body --cacert server.pem -H "X-Token: TOKEN" -H "Content-Type: application/octet-stream" --data-binary @backup.log "https://host/publication/hs/telemetry/file?name=backup.log"
Использовать переменную окружения вместо TOKEN в реальном скрипте, не публиковать её значение; для версий curl без --fail-with-body использовать --fail. Не ставить -k/--insecure. Отдельные исполняемые примеры и проверка PowerShell 5.1/Python/cURL — задача разработки.


Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
