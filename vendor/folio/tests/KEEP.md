# @keep security tests

These tests freeze the Folio 1.1.2 local HTTP security behaviour. They passed on `4e11cea`.
Later work packages (WP-13 in particular) may refactor `folio/web.py` and `folio/local_auth.py`, but
every test below must stay green **without editing the test or its golden**. A change that needs one of
them to change is a security decision and must be reviewed as such.

The ID appears in the test name (`test_keep_secNN_...`) and in its `@keep` docstring.
Goldens live in `tests/characterization/goldens/keep_*.json`.

Run them alone: `python3 -m unittest discover -s tests -p "test_http_security_keep.py" -v`

| ID | Test | Behaviour | Source |
| --- | --- | --- | --- |
| KEEP-SEC-01 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec01_unauthenticated_api_is_403` | Every `/api/*` read and write (state, backup, decisions, export, brief, clients, shutdown, PATCH, DELETE) without the owner token or a browser session returns 403 `FORBIDDEN`; nothing is saved and the server keeps running | `folio/web.py:61-70`, `folio/web.py:117-118` |
| KEEP-SEC-02 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec02_wrong_host_is_403` | A `Host` other than `127.0.0.1:<port>` or `localhost:<port>` returns 403 "Invalid local host." before authentication, on API and static paths | `folio/web.py:54-56`, `folio/web.py:204` |
| KEEP-SEC-03 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec03_foreign_origin_is_403` | An `Origin` other than `http://127.0.0.1:<port>` or `http://localhost:<port>` returns 403, even with the owner token and on the session bootstrap | `folio/web.py:57-59` |
| KEEP-SEC-04 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec04_non_json_write_is_415` | An authenticated write whose `Content-Type` is not `application/json` (parameters allowed) returns 415 and saves nothing | `folio/web.py:81-83` |
| KEEP-SEC-05 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec05_state_carries_no_credentials` | `/api/state` never contains the owner token, the browser launch token, the session cookie value or the session proof; it carries only `csrf_token` | `folio/web.py:134-137` |
| KEEP-SEC-06 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec06_session_cookie_attributes` | The session cookie is exactly `folio_session_<port>=<64 hex>; HttpOnly; SameSite=Strict; Path=/api`; the bootstrap accepts only the launch token (not the owner token) and sets no cookie on refusal | `folio/web.py:99-116`, `folio/web.py:205` |
| KEEP-SEC-07 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec07_csrf_on_browser_writes` | Browser-session writes need cookie + `X-Folio-Session` proof + `X-Workspace-Token` CSRF token; reads need cookie + proof; owner-token writes need no CSRF | `folio/web.py:64-70`, `folio/web.py:119-121` |
| KEEP-SEC-08 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec08_discovery_file_private_and_nofollow` | `.server.json` is a regular 0600 file with exactly `port, pid, started_at, owner_token, browser_token`; reads use `O_NOFOLLOW` and refuse symlinks, any other mode and a base URL for another host or port | `folio/local_auth.py:12-44`, `folio/web.py:217-229`, `folio/core.py:157-169` |
| KEEP-SEC-09 | `tests/characterization/test_http_security_keep.py::WorkspacePermissionsKeepTests::test_keep_sec09_workspace_permissions` | A new workspace is 0700 even under umask 002; a group- or other-writable workspace is refused with 403 and its mode untouched, and no discovery file is written; discovery is removed on close | `folio/core.py:237`, `folio/web.py:206-213`, `folio/web.py:179-182` |
| KEEP-SEC-10 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec10_credentials_rotate_on_restart` | A restart issues new owner, launch and CSRF tokens (all distinct), forgets every session, removes discovery on close, and old credentials are refused | `folio/web.py:198-202`, `folio/web.py:232-239` |
| KEEP-SEC-11 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec11_logs_exclude_bodies_queries_and_secrets` | The access log records method, path and status only: no request body, query string, header, cookie or token, also for refused and malformed requests | `folio/web.py:36-38` |
| KEEP-SEC-12 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec12_security_response_headers` | API, static, 403 and 404 responses carry the CSP, `nosniff`, `no-referrer` and `no-store` headers (golden) | `folio/web.py:40-52` |
| KEEP-SEC-13 | `tests/characterization/test_http_security_keep.py::HttpSecurityKeepTests::test_keep_sec13_loopback_only_bind` | The server binds 127.0.0.1 only; allowed hosts and the cookie name are scoped to its own port | `folio/web.py:194`, `folio/web.py:203-205` |
