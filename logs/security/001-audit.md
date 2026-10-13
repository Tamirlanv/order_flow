# S01 — аудит безопасности, 2026-10-13

Статус: локальные проверки и CI выполнены; пункт цены открыт до M03a. База аудита — M01/M02a, main `1b3f4bf`; исправления в `feature/security-hardening`, коммит `f4b3298`. Каталог, заказы и восстановление пароля ещё не реализованы. Пользовательские `docs/DESIGN.md` и `docs/README_example.md` не изменялись и не добавлялись в Git.

## Результат по шести пунктам

| № | Проверка | Результат и граница доказательства |
| --- | --- | --- |
| 1 | CSRF каждой изменяющей формы | PASS: 5 endpoints × 7 негативных случаев + cross-site form дают 403, без побочных эффектов; UI проверяет заголовок для каждого действия. Проверены также смена сессии и успешные сценарии |
| 2 | CSP / HSTS / X-Frame-Options | PASS после исправления: реальные HTTP-ответы Nginx и ошибки; отдельно 4 теста TLS с проверяемым сертификатом, Secure cookie, HSTS и redirect |
| 3 | Лимит аккаунта / X-Forwarded-For | PASS: смена transport IP, forwarding-заголовков, cookies, регистра email не обходит лимит; 11-я попытка 429, другой аккаунт 401 |
| 4 | Цена ноль/минус | **НЕ ПРОВЕРЕНО: функциональность отсутствует.** Для 0, -0.01, -1 — три явных skip. Внесено BR-11 и обязательные API/БД проверки на M03a |
| 5 | Существование зависимостей | PASS: 88 точных PyPI-релизов и 307 npm-релизов, включая транзитивные/optional; npm tarball/integrity совпадают. pip-audit и npm audit: известных уязвимостей не найдено |
| 6 | Ключи в Git | PASS: Gitleaks 8.30.1, полная доступная история `--all` и текущие неигнорируемые исходники; 0 находок. Локальный .env и сертификат не являются частью репозитория |

Это аудит текущих функций по заданным направлениям, а не гарантия отсутствия любых уязвимостей. Проверка реестра не доказывает добросовестность пакета, сканирование сигнатур не гарантирует обнаружение каждого секрета.

## SEC-001 — отсутствовали CSP и запрет iframe

**Подтверждение:** исходный ответ `/api/v1/system` не содержал Content-Security-Policy и X-Frame-Options; Server раскрывал `nginx/1.30.5`. Отсутствие frame-ancestors/X-Frame-Options оставляло интерфейс без защиты от встраивания. Эксплуатируемая XSS не обнаружена и не заявляется.

**Исправление:** в `frontend/nginx-security.conf` добавлены CSP (`default-src 'none'`, локальные scripts/styles/fonts, frame-ancestors none, base-uri none, form-action self), X-Frame-Options DENY, nosniff, Referrer-Policy, Permissions-Policy. `always` сохраняет заголовки на ошибках. `server_tokens off` скрывает версию. Swagger 5.33.2 поставляется локально, без CDN и inline JavaScript; backend CDN docs отключены. Swagger — режим просмотра, отправка mutations требует полноценного CSRF клиента.

**Проверка:** `test_nginx_security_headers_http` проверяет UI, docs, OpenAPI, API, 401/404; отдельный тест проверяет 403/413. `test_swagger_and_ui_have_only_local_scripts_and_styles` проверяет локальные assets. Браузерный smoke: обзор, аккаунт, раскрытие операции Swagger — ошибок CSP/console не было.

Фактические заголовки после исправления:

```text
Content-Security-Policy=default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'
X-Frame-Options=DENY
X-Content-Type-Options=nosniff
Referrer-Policy=no-referrer
Server=nginx
```

## SEC-002 — не было конфигурации HTTPS/HSTS

**Подтверждение:** единственный Nginx listener — HTTP 80; опубликован 8080. Это допустимый локальный режим, но не защита транспорта для публичного доступа.

**Исправление:** `compose.https.yaml`, `nginx-https.conf`, `scripts/init-local-tls.ps1`. TLS 1.2/1.3, HSTS max-age=31536000 только при реальном TLS, редирект HTTP на фиксированный localhost:8443 без использования недоверенного Host. Сертификат не попадает в Git, доверие в ОС не устанавливается. X-Forwarded-Proto=https по HTTP не включает HSTS. Secure cookies определяются доверенной конфигурацией PUBLIC_APP_URL.

**Проверка:** `test_nginx_hsts_over_verified_tls` и `test_https_redirect_csrf_and_secure_cookie`. Использован `ssl.create_default_context(cafile=...)`; verify=False не применяется. Проверены успешный TLS, 404 с заголовками, Secure/HttpOnly cookie, CSRF logout 204, redirect с подменённым Host.

```powershell
./scripts/init-local-tls.ps1
docker compose -f compose.yaml -f compose.https.yaml --profile app up -d --no-build --wait
docker compose -f compose.yaml -f compose.https.yaml --profile app --profile test run --rm --no-deps tests python -m pytest -q tests/test_security_gateway.py -k 'hsts or https_redirect'
```

```text
4 passed, 13 deselected in 0.96s
```

**Ограничение:** самоподписанный сертификат не доверен браузером по умолчанию; HSTS не объявляется работающим в браузере с недоверенным сертификатом. Для публичного домена нужны доверенный сертификат и отдельная конфигурация. После теста восстановлен HTTP localhost:8080; его нельзя считать HTTPS-защищённым.

## SEC-003 — стандартный access log содержал строку запроса

**Подтверждение:** в исходном Nginx не был переопределён стандартный формат. Он содержит URI/query и IP; секрет, случайно переданный в query, мог попасть в журнал. Реальная утечка пользовательского токена не обнаружена. Существующие verification-ссылки используют fragment и сами по себе на сервер не отправляются.

**Исправление:** access log — JSON только request_id/status/bytes/duration. Per-request error log отключён, поскольку может содержать raw request line; startup/config ошибки остаются в глобальном stderr. Uvicorn access log уже был отключён. Это осознанное ограничение диагностики; расширять её на M09 только с безопасными полями.

**Проверка:** `scripts/check-nginx-logs.ps1` отправляет уникальный безопасный маркер в query, Authorization, cookie и большое тело; затем читает только свежие журналы, требует JSON-записи и отсутствие маркера. Скрипт не печатает исходные журналы.

```text
Nginx/API logs PASS: query, authorization, cookie and rejected request body absent; safe JSON records present.
```

## SEC-004 — для auth действовал общий лимит тела 6 MiB

**Подтверждение:** исходный Nginx пропускал тело 17 000 байт к API вместо раннего 413; исходный тест провалился. Это избыточный бюджет обработки, не доказательство успешной DoS-атаки.

**Исправление:** `/api/v1/auth/` ограничен 16 KiB; client header/body timeout 10 секунд, proxy connect timeout 3 секунды, proxy read/send timeout 30 секунд. Будущий импорт имеет отдельный общий бюджет 6 MiB.

**Проверка:** `test_nginx_rejects_large_auth_body_and_fake_https`: тело 17 000 байт → 413 с защитными заголовками; без CSRF → 403.

## SEC-005 — forwarding-цепочка была неявной

**Подтверждение:** Nginx дописывал клиентский X-Forwarded-For через proxy_add_x_forwarded_for. Рабочий обход лимита входа не обнаружен: лимит email уже существовал. Риск — последующая ошибочная настройка доверия proxy.

**Исправление:** edge заменяет X-Forwarded-For/X-Real-IP адресом соединения, удаляет Forwarded; Uvicorn явно запускается с --no-proxy-headers. Лимит email не ослаблен. Дополнительный IP-лимит пока общий для клиентов proxy; перед публичным развёртыванием нужно отдельно решить справедливое доверенное определение адресов.

**Проверка:** `test_account_limit_survives_ip_xff_case_and_cookie_changes` использует настоящие PostgreSQL/Redis, отдельные ASGI transport peers и cookie jars. 10 неуспешных попыток, следующая блокируется; новый аккаунт с нового peer не заблокирован. Это проверка API/Redis с моделируемыми peer-адресами, не распределённая сетевая атака.

## SEC-006 — отсутствовал автоматический контроль зависимостей и секретов

**Класс:** пробел процесса, а не найденный вредоносный пакет или утёкший ключ.

**Исправление:** `check-dependencies.mjs` проверяет lock-файлы в официальных реестрах, отклоняет неизвестные/неполные записи и сетевые ошибки. Три Node-теста проверяют fail-closed поведение, scoped/nested/optional пакеты. Добавлены pip-audit, npm audit и Gitleaks в CI. Gitleaks скачивается из официального релиза 8.30.1 с закреплёнными SHA-256 для Windows/Linux x64. Сканирует историю всех refs и снимок текущих tracked/untracked неигнорируемых исходников; широких allowlist нет. Сырые JSON с redaction — только `.tmp/security/`.

```powershell
node --test scripts/check-dependencies.test.mjs
node scripts/check-dependencies.mjs
backend/.venv/Scripts/python.exe -m pip_audit --disable-pip --no-deps -r backend/requirements.lock -r backend/requirements-dev.lock
npm --prefix frontend audit --audit-level=low
./scripts/install-gitleaks.ps1
node scripts/check-secrets.mjs
```

Выдержки фактического вывода:

```text
tests 3
pass 3
fail 0
PyPI: 88 exact releases verified
npm: 307 exact releases, tarballs and integrity verified
Dependency registry check: PASS (existence is not a malware/security guarantee)
No known vulnerabilities found
found 0 vulnerabilities
Gitleaks 8.30.1 installed; pinned SHA-256 verified.
INF 7 commits scanned.
INF no leaks found
INF no leaks found
Gitleaks PASS: all Git refs/history + 97 current source files; 0 findings
```

Сканирование выполнено до коммита этого отчёта; после коммита количество просмотренных коммитов меняется, CI повторяет сканирование. `pip-audit --no-deps` использует полные pinned runtime/dev lock-файлы; pip-audit рекомендует также хэши Python-пакетов. Python lock пока без хэшей, Docker base images без digest pinning — оставшиеся меры защиты цепочки поставки. Container OS CVE scan не выполнялся.

## SEC-007 — dotfile-пути попадали в SPA fallback

**Подтверждение:** запросы `/.env` и `/.git/config` возвращали HTML оболочку со статусом 200; реальное содержимое секретных файлов не выдавалось. Это неточный ответ и отсутствие явного запрета, не подтверждённая утечка.

**Исправление:** `location ~ /\.` возвращает 404; оба пути включены в тесты заголовков. Секреты по-прежнему исключены из Git и build context; дополнительно исключён вложенный Python bytecode из Docker context.

## SEC-008 — install-телеметрия транзитивного Swagger-пакета

**Обнаружено при review нового lock:** Swagger UI включает `@scarf/scarf` с install hook. Это механизм аналитики установок, не известная CVE. Данных приложения ему отправлять не требуется.

**Исправление:** `scarfSettings.enabled=false` в корневом frontend package.json; дополнительно `SCARF_ANALYTICS=false` в build-стадии Docker. Отключение соответствует README и коду установленного официального пакета. Аналитика не нужна проекту; сам Swagger поставляется и работает локально.

Проверка штатного npm hook с отключённой аналитикой (`SCARF_ANALYTICS=false`, `SCARF_VERBOSE=true`, `npm rebuild @scarf/scarf --foreground-scripts`):

```text
Error: Scarf has been disabled via a package.json in the dependency chain.
rebuilt dependencies successfully
```

Сообщение Error здесь — штатный отказ Scarf отправлять аналитику; npm завершился успешно. Первоначальный прямой вызов report.js вне npm не проверил настройку из-за отсутствия npm environment; поэтому проверка повторена штатным npm hook.

## CSRF — существующая защита подтверждена

Тест `test_every_mutation_requires_bound_csrf_and_origin`: register, login, verification/request, verification/confirm, logout. Для каждого — пустой/чужой токен, чужой/null/пустой Origin, чужая cookie, отсутствие cookie. Отдельно обычная cross-site HTML-форма. Проверяются 403 и отсутствие User/Session/письма. Имеющийся тест проверяет старый CSRF после смены сессии; успешные register/confirm/login/me/logout остаются покрыты.

Вывод окончательного прогона `pytest -q -s`:

```text
CSRF: 5 endpoints x 7 invalid cases + cross-site form -> 403; no users/sessions/mail created
Account limit with fresh IP/cookie/XFF and email case changes: [401, 401, 401, 401, 401, 401, 401, 401, 401, 401, 429, 401]
43 passed, 7 skipped in 25.51s
```

`AuthPanel.test.tsx` проверяет передачу X-CSRF-Token каждым действием; `auth-api.test.ts` запрещает отправку любого из 5 POST при сбое получения CSRF. Скрытое поле формы не добавлено: SPA отправляет токен в заголовке, сервер его проверяет.

## Цена — открытый пункт, не успешная проверка

```powershell
docker compose --profile app --profile test run --rm --no-deps tests python -m pytest -q tests/test_security_gateway.py -k catalog -rs
```

Тест `test_catalog_rejects_non_positive_price` входит в общий выполненный прогон; фактические причины skip:

```text
M03a not implemented: no product/price API to submit price=0
M03a not implemented: no product/price API to submit price=-0.01
M03a not implemented: no product/price API to submit price=-1
```

При появлении price в OpenAPI guard требует заменить skip реальными POST/PATCH/БД-тестами. На M03a: Decimal > 0, NUMERIC(14,2), CHECK(price > 0), проверка создания/изменения/импорта. Критерий пользователя «сервер не принимает цену ноль и меньше» пока не подтверждён.

## Общие проверки и воспроизведение

До исправления:

```powershell
docker compose --profile app --profile test run --rm --no-deps tests python -m pytest -q tests/test_security_gateway.py -k 'http or large' --tb=no
```

```text
9 failed, 1 skipped, 7 deselected in 1.16s
```

После исправлений выполнены Docker build, Nginx -t, полный HTTP-набор, отдельный TLS-набор, UI-тесты и `./scripts/check.ps1`:

```text
nginx: configuration file /etc/nginx/nginx.conf test is successful
43 passed, 7 skipped in 26.15s
4 passed, 13 deselected in 0.96s
Tests 14 passed (14)
16 passed, 34 skipped in 1.74s
All checks passed!
Success: no issues found in 17 source files
Documentation links and formatting: 14 files passed
Source checks passed. Containers and live infrastructure were not tested.
```

Последняя строка относится только к `check.ps1`; контейнеры отдельно проверены командами выше. Из 7 HTTP-skip: 4 — отдельный TLS-прогон, 3 — отсутствующий каталог. В локальном pytest без Compose 34 skip ожидаемы. Миграции проверены на временной БД в полном наборе, основная БД не удалялась. Первоначальный локальный pytest в ограниченной песочнице прерван после зависания, успешный повтор выполнен с доступом; первый Ruff-прогон поймал длинную строку в новом тесте, она исправлена, весь check.ps1 повторён.

Сборка предупреждает о размере отдельного Swagger bundle (~1.47 MB до gzip); это не ошибка CSP и bundle не включён в основную страницу. CI запускает backend/frontend/configuration/integration/security. Публичного deploy/publish образов нет.

[GitHub Actions № 38358314408](https://github.com/Tamirlanv/order_flow/actions/runs/38358314408), коммит `f4b3298`: **success**, все пять jobs пройдены. Linux CI независимо повторил HTTP/TLS, безопасные журналы, проверку реестров, advisory и Gitleaks на закоммиченной версии. После отключения install-телеметрии локально пересобран frontend: `10 passed, 3 skipped, 4 deselected in 1.08s` для HTTP gateway/цены; TLS повторён CI.

## Источники и дальнейшая работа

Источники пользователя использованы как направления проверки, их статистика не переносится на OrderFlow: [Tenzai](https://www.tenzai.com/blog/bad-vibes-comparing-the-secure-coding-capabilities-of-popular-coding-agents), [исследование пакетов](https://arxiv.org/abs/2406.10279), [GitGuardian 2025](https://www.gitguardian.com/state-of-secrets-sprawl-report-2025), [исследование инструкций безопасности](https://arxiv.org/abs/2512.03262).

Технические основания: [OWASP CSRF](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), [Nginx add_header/always](https://nginx.org/en/docs/http/ngx_http_headers_module.html), [MDN HSTS](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Strict-Transport-Security), [Gitleaks](https://github.com/gitleaks/gitleaks).

Дальше: M02b права/изоляция магазинов, M02c восстановление пароля; на M03a закрыть тест цен. Эти будущие бизнес-модули не считаются проверенными этим аудитом. Перед публичным развёртыванием нужны доверенный TLS, настройка proxy/IP-limit, отдельные production-секреты и повторная проверка актуальной версии.
