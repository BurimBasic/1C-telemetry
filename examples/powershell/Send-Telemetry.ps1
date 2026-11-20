# 1C-telemetry. Один HTTPS-запрос из Windows PowerShell 5.1.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
# Mode: ping, json или file. Path: исходный файл для json/file.
# TLM_URL и TLM_TOKEN задаёт оператор. Результат: HTTP-код и ID или исключение.
# Пример: .\Send-Telemetry.ps1 file 'C:\Backup\отчёт.log'
param(
    [Parameter(Mandatory = $true)][ValidateSet('ping','json','file')][string]$Mode,
    [string]$Path
)
$ErrorActionPreference = 'Stop'
$base = [Uri]$env:TLM_URL
if (-not $base.IsAbsoluteUri -or $base.Scheme -ne 'https' -or $base.UserInfo -or $base.Query -or $base.Fragment) {
    throw 'Укажите HTTPS URL без параметров и данных входа в TLM_URL.'
}
if ($env:TLM_TOKEN -cnotmatch '^[0-9a-f]{64}$') { throw 'Укажите токен отправителя в TLM_TOKEN.' }
$arguments = @{
    Uri = $base.AbsoluteUri.TrimEnd('/') + '/' + $Mode
    Method = 'Get'
    Headers = @{'X-Token' = $env:TLM_TOKEN; Accept = 'application/json'}
    UseBasicParsing = $true
    MaximumRedirection = 0
    TimeoutSec = 60
}
if ($Mode -ne 'ping') {
    $file = Get-Item -LiteralPath $Path
    if ($file.PSIsContainer) { throw 'Укажите путь к файлу.' }
    $arguments.Method = 'Post'
    $arguments.InFile = $file.FullName
    if ($Mode -eq 'file') {
        $arguments.Uri += '?name=' + [Uri]::EscapeDataString($file.Name)
        $arguments.ContentType = 'application/octet-stream'
    } else {
        $arguments.ContentType = 'application/json; charset=utf-8'
    }
}
try {
    $response = Invoke-WebRequest @arguments
    $body = $response.Content | ConvertFrom-Json
} catch {
    $http = $_.Exception.Response
    if ($http -and [int]$http.StatusCode -ge 400 -and [int]$http.StatusCode -lt 500) {
        throw "Запрос отклонён, HTTP $([int]$http.StatusCode)."
    }
    throw 'Запрос не подтверждён. Проверьте HTTPS, связь и журнал приёма.'
}
$expected = if ($Mode -eq 'ping') { 200 } else { 201 }
$id = $body.id
if ([int]$response.StatusCode -ne $expected -or $body.ok -isnot [bool] -or -not $body.ok -or
    ($Mode -eq 'ping' -and $null -ne $id) -or
    ($Mode -ne 'ping' -and $id -notmatch '^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$')) {
    throw "Ответ не подтверждает операцию. HTTP $([int]$response.StatusCode)."
}
[pscustomobject]@{ Http = [int]$response.StatusCode; Id = $id }

# 1C-telemetry. Конец Send-Telemetry.ps1.
# Copyright © 2026 Тарасов Роман Олегович. Все права защищены.
