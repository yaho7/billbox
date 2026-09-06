# Billbox Docker Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted personal bookkeeping application that runs the existing China Merchants Bank email automation, a normalized SQLite ledger, a protected FastAPI API, and a shadcn React interface in one Docker image.

**Architecture:** A single container serves the compiled Vite application through FastAPI and runs a guarded in-process scheduler for IMAP ingestion. SQLite under `/data` is the only source of truth; accounts, categories, transactions, source receipts, audit entries, and job runs are separate tables. GitHub Actions reacts to every push to `main`, verifies and builds the image in GitHub, and publishes `main` plus immutable commit-SHA image tags to GHCR without creating Git tags or deploying the container.

**Tech Stack:** Python 3.13, FastAPI, standard-library SQLite, APScheduler, IMAP, React, TypeScript, Vite, Tailwind CSS, shadcn/ui, Vitest, pytest, Docker, GitHub Actions, GHCR.

---

## File Structure

- `backend/billbox/config.py`: validates secrets, data paths, IMAP settings, schedule, and session policy.
- `backend/billbox/db.py`: opens SQLite connections with WAL/foreign keys and applies ordered SQL migrations.
- `backend/billbox/ledger.py`: performs account/category/transaction commands, filters, dashboard aggregation, and audit recording.
- `backend/billbox/auth.py`: creates and verifies signed HTTP-only sessions and CSRF tokens.
- `backend/billbox/api.py`: exposes the authenticated FastAPI application and serves the compiled SPA.
- `backend/billbox/imap_client.py`: downloads messages with stable IMAP UID identity and verified TLS.
- `backend/billbox/parsers.py`: parses China Merchants Bank credit-card and debit-card notices into domain candidates.
- `backend/billbox/ingestion.py`: claims source messages idempotently, persists transactions, and records job progress.
- `backend/billbox/scheduler.py`: starts one configurable ingestion schedule and prevents overlapping runs.
- `backend/billbox/main.py`: FastAPI entry point and lifespan wiring.
- `migrations/001_initial.sql`: normalized ledger schema, constraints, indexes, and starter categories.
- `frontend/src/`: Vite application, API client, shadcn components, dashboard, transaction list, correction dialog, and automation status.
- `tests/backend/`: database, API, parser, ingestion, scheduler, and authentication tests.
- `frontend/src/**/*.test.tsx`: page interaction and accessibility-oriented component tests.
- `Dockerfile`, `docker/entrypoint.sh`, `compose.yaml`: multi-stage image definition and persistent runtime configuration.
- `.github/workflows/image.yml`: push-triggered checks and GHCR image publication.

## Data Model Contract

`amount_minor` is always a positive integer number of cents. `kind` carries the economic meaning (`expense`, `income`, `refund`, `transfer`, or `repayment`) and remains independent from category. An automation message is identified by `(provider, mailbox, uid_validity, uid)`; a parsed transaction is identified by the message plus a deterministic item key. Manual records use a generated UUID source key.

```sql
CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL CHECK (kind IN ('cash','debit','credit','investment','other')),
  currency TEXT NOT NULL DEFAULT 'CNY' CHECK (length(currency) = 3),
  archived_at TEXT
);
CREATE TABLE categories (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  scope TEXT NOT NULL CHECK (scope IN ('expense','income','both')),
  archived_at TEXT
);
CREATE TABLE source_records (
  id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  mailbox TEXT NOT NULL,
  uid_validity INTEGER NOT NULL,
  uid INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  subject TEXT NOT NULL DEFAULT '',
  received_at TEXT,
  state TEXT NOT NULL CHECK (state IN ('claimed','processed','ignored','failed')),
  error TEXT,
  raw_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (provider, mailbox, uid_validity, uid)
);
CREATE TABLE transactions (
  id TEXT PRIMARY KEY,
  source_record_id TEXT REFERENCES source_records(id) ON DELETE SET NULL,
  source_key TEXT NOT NULL UNIQUE,
  account_id TEXT NOT NULL REFERENCES accounts(id),
  category_id TEXT REFERENCES categories(id),
  kind TEXT NOT NULL CHECK (kind IN ('expense','income','refund','transfer','repayment')),
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  currency TEXT NOT NULL DEFAULT 'CNY' CHECK (length(currency) = 3),
  merchant TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  channel TEXT NOT NULL DEFAULT '',
  occurred_at TEXT NOT NULL,
  review_state TEXT NOT NULL DEFAULT 'pending' CHECK (review_state IN ('pending','confirmed')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE transaction_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  transaction_id TEXT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT NOT NULL,
  actor TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE job_runs (
  id TEXT PRIMARY KEY,
  job_name TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('running','succeeded','failed')),
  started_at TEXT NOT NULL,
  finished_at TEXT,
  summary_json TEXT NOT NULL DEFAULT '{}',
  log_text TEXT NOT NULL DEFAULT '',
  error TEXT
);
```

## API Contract

- `POST /api/auth/login`: accepts `{ "password": "..." }`, applies rate limiting per process, and sets a signed HTTP-only `SameSite=Strict` session cookie.
- `POST /api/auth/logout`: clears the session cookie.
- `GET /api/session`: returns authentication state plus the per-session CSRF token after login.
- `GET /api/dashboard?month=YYYY-MM`: returns net cash flow, expense, income, review count, monthly series, and category totals.
- `GET /api/transactions`: accepts `query`, `account`, `category`, `kind`, `date_from`, `date_to`, and `page`; returns 25 rows and filter metadata.
- `POST /api/transactions`: creates a manual record and its audit entry; requires session and `X-CSRF-Token`.
- `PATCH /api/transactions/{id}`: changes category, note, or review state and records before/after JSON; requires session and `X-CSRF-Token`.
- `GET /api/options`: returns active accounts and categories.
- `GET /api/jobs/latest`: returns the latest ingestion state and bounded log.
- `POST /api/jobs/ingest`: starts one non-overlapping ingestion job; requires session and `X-CSRF-Token`.
- `GET /healthz`: checks the database and remains unauthenticated for Docker health checks.

## Frontend Design Direction

The product is a private bank-email ledger for one owner. Its primary job is to make monthly cash movement scannable and make uncertain classifications easy to correct.

- Color: `Ledger ink #17263C`, `Cool paper #F3F6F5`, `Sheet #FFFFFF`, `Expense coral #B84E48`, `Income jade #25745C`, `Review amber #9A681C`. Components consume these through shadcn semantic tokens instead of raw utility colors.
- Type: the local Chinese system sans stack for privacy and zero font requests; large monthly figures use tabular numerals and tighter tracking, while labels remain sentence case.
- Layout: a single dark ledger band carries the month result; below it, a wide transaction workspace sits beside a narrow classification ledger instead of a repeated SaaS card grid.
- Principles: one memorable ledger band, quiet surrounding surfaces, no decorative gradients, URLs own filter state, controls retain visible labels, and mobile replaces the desktop table with readable transaction sheets.

```text
Desktop
┌ Billbox ─────── 本月账本 / 自动抓取状态 ─────── 新增记录 ┐
├──────────────────────────────────────────────────────────┤
│  2026 年 9 月        本月结余        支出        收入     │
│                       ¥ 2,418.30     ¥ 812.70   ¥ 3,231 │
├───────────────────────────────────┬──────────────────────┤
│  筛选器 + 交易表                   │  分类去向 / 待确认    │
│  日期  商户  类型  分类  金额      │  餐饮  █████         │
│  …                                │  交通  ███           │
└───────────────────────────────────┴──────────────────────┘

Mobile
┌ Billbox                    新增 ┐
│ 本月结余 ¥2,418.30              │
│ 支出 ¥812.70   收入 ¥3,231.00   │
├ 筛选 ───────────────────────────┤
│ 商户                 -¥18.00    │
│ 9月6日 · 餐饮 · 已确认           │
│ …                               │
└─────────────────────────────────┘
```

Generic-default review: the first draft used four equal summary cards and a decorative gradient, which would read as a generic dashboard. The revised design consolidates totals into one ledger band and uses the remaining space for real review work; the only strong visual treatment is the monthly figure.

### Task 1: Establish the normalized SQLite ledger

**Files:**
- Create: `tests/backend/test_db.py`
- Create: `tests/backend/test_ledger.py`
- Create: `backend/billbox/db.py`
- Create: `backend/billbox/ledger.py`
- Create: `migrations/001_initial.sql`

- [ ] **Step 1: Write failing schema and ledger tests**

```python
def test_amount_is_positive_and_kind_is_separate(ledger):
    transaction = ledger.create_manual_transaction({
        "account_id": "cash",
        "kind": "expense",
        "amount": "18.90",
        "merchant": "早餐店",
        "occurred_at": "2026-09-06T08:30:00+08:00",
    })
    assert transaction["amount_minor"] == 1890
    assert transaction["kind"] == "expense"

def test_same_source_key_is_idempotent(ledger):
    first = ledger.add_automation_transaction(source_key="mail:42:1", amount_minor=1890)
    second = ledger.add_automation_transaction(source_key="mail:42:1", amount_minor=1890)
    assert first["id"] == second["id"]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/backend/test_db.py tests/backend/test_ledger.py -q`

Expected: collection fails because `billbox.db` and `billbox.ledger` do not exist.

- [ ] **Step 3: Implement migration and repository**

Implement the SQL contract above, connection pragmas `foreign_keys=ON`, `journal_mode=WAL`, `busy_timeout=5000`, decimal-to-minor conversion, idempotent source keys, parameterized filters, audit transactions, and bounded job logs.

- [ ] **Step 4: Run focused tests and commit**

Run: `python3 -m pytest tests/backend/test_db.py tests/backend/test_ledger.py -q`

Expected: all ledger tests pass.

Commit: `feat: add normalized sqlite ledger`

### Task 2: Add the protected FastAPI surface

**Files:**
- Create: `tests/backend/test_auth.py`
- Create: `tests/backend/test_api.py`
- Create: `backend/billbox/config.py`
- Create: `backend/billbox/auth.py`
- Create: `backend/billbox/api.py`
- Create: `backend/billbox/main.py`

- [ ] **Step 1: Write failing route tests**

```python
def test_ledger_requires_login(client):
    response = client.get("/api/dashboard?month=2026-09")
    assert response.status_code == 401

def test_mutation_requires_csrf(authenticated_client):
    response = authenticated_client.post("/api/transactions", json={})
    assert response.status_code == 403

def test_manual_transaction_round_trip(authenticated_client, csrf_token):
    created = authenticated_client.post(
        "/api/transactions",
        headers={"X-CSRF-Token": csrf_token},
        json={"account_id":"cash","kind":"expense","amount":"18.90","merchant":"早餐店","occurred_at":"2026-09-06T08:30:00+08:00"},
    )
    assert created.status_code == 201
    assert authenticated_client.get("/api/transactions?query=早餐店").json()["total"] == 1
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/backend/test_auth.py tests/backend/test_api.py -q`

Expected: collection fails because the FastAPI application does not exist.

- [ ] **Step 3: Implement auth and routes**

Use an HMAC-SHA256 signed session payload with expiry and random CSRF value, `HttpOnly`, `Secure` when configured, and `SameSite=Strict`. Validate all request bodies with Pydantic, compare secrets with `secrets.compare_digest`, keep SQL out of route handlers, and return actionable Chinese errors.

- [ ] **Step 4: Run focused tests and commit**

Run: `python3 -m pytest tests/backend/test_auth.py tests/backend/test_api.py -q`

Expected: all API tests pass.

Commit: `feat: add protected ledger api`

### Task 3: Move mail automation into the application

**Files:**
- Create: `tests/backend/test_parsers.py`
- Create: `tests/backend/test_ingestion.py`
- Create: `tests/backend/test_scheduler.py`
- Create: `backend/billbox/imap_client.py`
- Create: `backend/billbox/parsers.py`
- Create: `backend/billbox/ingestion.py`
- Create: `backend/billbox/scheduler.py`
- Modify: `backend/billbox/main.py`

- [ ] **Step 1: Write failing parser and idempotency tests**

```python
def test_credit_purchase_becomes_positive_minor_expense():
    rows = CMBCreditParser().parse("2026/09/06 08:30:00 CNY 18.90 尾号1234 消费 早餐店", datetime(2026, 9, 6))
    assert rows[0].kind == "expense"
    assert rows[0].amount_minor == 1890

def test_processed_uid_is_not_parsed_twice(ingestion, fake_mail):
    assert ingestion.ingest(fake_mail) == "processed"
    assert ingestion.ingest(fake_mail) == "duplicate"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/backend/test_parsers.py tests/backend/test_ingestion.py tests/backend/test_scheduler.py -q`

Expected: collection fails because the ingestion modules do not exist.

- [ ] **Step 3: Implement verified-TLS IMAP ingestion**

Port only the two proven CMB parser formats, remove IP hard-coding and certificate bypass, search by stable UID, persist failures for retry, record one source receipt per message, derive deterministic item keys, and prevent scheduler overlap with a process lock. The scheduler defaults to `03:30` Asia/Shanghai and is disabled unless mail credentials are present.

- [ ] **Step 4: Run focused tests and commit**

Run: `python3 -m pytest tests/backend/test_parsers.py tests/backend/test_ingestion.py tests/backend/test_scheduler.py -q`

Expected: parser, ingestion, and scheduler tests pass.

Commit: `feat: run bank mail ingestion in container`

### Task 4: Build the shadcn ledger interface

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/components.json`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/app.tsx`
- Create: `frontend/src/features/auth/login-page.tsx`
- Create: `frontend/src/features/dashboard/dashboard-page.tsx`
- Create: `frontend/src/features/transactions/transaction-list.tsx`
- Create: `frontend/src/features/transactions/transaction-form.tsx`
- Create: `frontend/src/features/jobs/job-status.tsx`
- Create: `frontend/src/**/*.test.tsx`
- Create through shadcn CLI: `frontend/src/components/ui/*`

- [ ] **Step 1: Initialize Vite and shadcn project context**

Run the official CLI in `frontend/`, then inspect `npx shadcn@latest info --json`. Search the `@shadcn` registry and fetch current docs before adding `button`, `card`, `badge`, `table`, `dialog`, `field`, `input`, `select`, `tabs`, `toggle-group`, `alert`, `empty`, `skeleton`, `sonner`, and `chart`.

- [ ] **Step 2: Write failing interaction tests**

```tsx
it("keeps transaction filters in the URL", async () => {
  render(<App />, { wrapper: TestProviders })
  await user.type(screen.getByLabelText("搜索交易"), "早餐店")
  await user.click(screen.getByRole("button", { name: "应用筛选" }))
  expect(window.location.search).toContain("query=%E6%97%A9%E9%A4%90%E5%BA%97")
})

it("labels every manual-entry control", () => {
  render(<TransactionForm />)
  expect(screen.getByLabelText("金额")).toBeVisible()
  expect(screen.getByLabelText("账户")).toBeVisible()
  expect(screen.getByLabelText("发生时间")).toBeVisible()
})
```

- [ ] **Step 3: Run frontend tests and verify RED**

Run: `npm test -- --run`

Expected: tests fail because the feature components are missing.

- [ ] **Step 4: Implement the reviewed design**

Compose shadcn primitives rather than custom controls. Use `FieldGroup`/`Field` for forms, `Badge` for states, `Table` for desktop records, `Dialog` for create/correct flows, `Empty` and `Skeleton` for data states, `Chart` for category totals, and `sonner` with polite live announcements. Use `Intl.DateTimeFormat` and `Intl.NumberFormat`, visible focus, a skip link, URL-backed filters, explicit labels, reduced motion, touch targets, and long-content truncation.

- [ ] **Step 5: Run tests, typecheck, and guidelines audit; then commit**

Run: `npm test -- --run`

Run: `npm run typecheck`

Fetch the current Web Interface Guidelines and review all `frontend/src/**/*.{tsx,css}` files in `file:line` format; fix every finding and repeat the two checks.

Expected: tests and no-emit typecheck pass, and the final UI audit reports no remaining findings.

Commit: `feat: add shadcn bookkeeping interface`

### Task 5: Package and publish the Docker image on push

**Files:**
- Create: `tests/backend/test_deployment_contract.py`
- Create: `Dockerfile`
- Create: `.dockerignore`
- Create: `docker/entrypoint.sh`
- Create: `compose.yaml`
- Create: `.env.example`
- Create: `.github/workflows/image.yml`
- Modify: `README.md`

- [ ] **Step 1: Write failing deployment contract tests**

```python
def test_compose_persists_sqlite(compose_text):
    assert "/data" in compose_text
    assert "DATABASE_PATH=/data/billbox.db" in compose_text

def test_action_only_publishes_images_from_main(workflow):
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "tags" not in workflow["on"]
    assert "docker/build-push-action" in workflow_text
    assert "deploy" not in workflow["jobs"]
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 -m pytest tests/backend/test_deployment_contract.py -q`

Expected: tests fail because Docker and workflow files do not exist.

- [ ] **Step 3: Add runtime packaging and push-only workflow**

Use a Node build stage, a Python runtime stage, non-root execution, `/data` volume, init-time migrations, and `/healthz`. The workflow uses current stable official GitHub and Docker actions, runs backend/frontend tests and no-emit typecheck, builds only in GitHub, and publishes `ghcr.io/<owner>/<repo>:main` plus `:sha-<commit>`; it never deploys and never creates a Git tag.

- [ ] **Step 4: Validate without a local image build and commit**

Run: `python3 -m pytest -q`

Run: `cd frontend && npm test -- --run && npm run typecheck`

Run: `python3 -c 'import ast, pathlib; [ast.parse(path.read_text()) for path in pathlib.Path("backend").rglob("*.py")]'`

Run: `sh -n docker/entrypoint.sh`

Run: `git diff --check`

Expected: all tests/static checks pass. Do not run `docker build`, `npm run build`, or any packaging command locally.

Commit: `ops: publish docker image from main pushes`

### Task 6: Final verification

- [ ] Re-run the complete backend test suite, frontend test suite, no-emit typecheck, Python AST parsing, shell syntax check, workflow/Compose contract tests, and `git diff --check`.
- [ ] Review `git status --short`; confirm `.DS_Store` remains untracked and every requested file is committed.
- [ ] Review `git log --oneline`; confirm each functional unit has its own rollback point on `main`.
- [ ] Do not claim that an image was built or deployed locally; only the repository-side contracts are verifiable without pushing to GitHub and configuring runtime secrets.
