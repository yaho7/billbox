CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL
        CHECK (kind IN ('cash', 'debit', 'credit', 'investment', 'other')),
    currency TEXT NOT NULL DEFAULT 'CNY' CHECK (length(currency) = 3),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TEXT
);

CREATE TABLE categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL CHECK (scope IN ('expense', 'income', 'both')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
    state TEXT NOT NULL DEFAULT 'claimed'
        CHECK (state IN ('claimed', 'processed', 'ignored', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 1 CHECK (attempt_count > 0),
    error TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider, mailbox, uid_validity, uid)
);

CREATE INDEX source_records_retry_idx
    ON source_records (state, provider, mailbox, updated_at);

CREATE TABLE transactions (
    id TEXT PRIMARY KEY,
    source_record_id TEXT REFERENCES source_records(id) ON DELETE SET NULL,
    source_key TEXT NOT NULL UNIQUE,
    account_id TEXT NOT NULL REFERENCES accounts(id),
    category_id TEXT REFERENCES categories(id),
    kind TEXT NOT NULL
        CHECK (kind IN ('expense', 'income', 'refund', 'transfer', 'repayment')),
    amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
    currency TEXT NOT NULL DEFAULT 'CNY' CHECK (length(currency) = 3),
    merchant TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL,
    review_state TEXT NOT NULL DEFAULT 'pending'
        CHECK (review_state IN ('pending', 'confirmed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX transactions_occurred_at_idx
    ON transactions (occurred_at DESC);
CREATE INDEX transactions_account_idx
    ON transactions (account_id, occurred_at DESC);
CREATE INDEX transactions_category_idx
    ON transactions (category_id, occurred_at DESC);
CREATE INDEX transactions_review_idx
    ON transactions (review_state, occurred_at DESC);

CREATE TABLE transaction_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id TEXT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    action TEXT NOT NULL CHECK (action IN ('created', 'updated')),
    before_json TEXT,
    after_json TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX transaction_audit_transaction_idx
    ON transaction_audit (transaction_id, id);

CREATE TABLE job_runs (
    id TEXT PRIMARY KEY,
    job_name TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('running', 'succeeded', 'failed')),
    started_at TEXT NOT NULL,
    finished_at TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}',
    log_text TEXT NOT NULL DEFAULT '',
    error TEXT
);

CREATE INDEX job_runs_latest_idx ON job_runs (job_name, started_at DESC);

INSERT INTO accounts (id, name, kind) VALUES
    ('cash', '现金', 'cash'),
    ('cmb-debit', '招商银行储蓄卡', 'debit'),
    ('cmb-credit', '招商银行信用卡', 'credit');

INSERT INTO categories (id, name, scope) VALUES
    ('food', '餐饮美食', 'expense'),
    ('daily', '日用百货', 'expense'),
    ('transport', '交通出行', 'expense'),
    ('housing', '居住物业', 'expense'),
    ('health', '医疗健康', 'expense'),
    ('education', '教育培训', 'expense'),
    ('culture', '文化休闲', 'expense'),
    ('digital', '数码电器', 'expense'),
    ('service', '生活服务', 'expense'),
    ('finance', '投资理财', 'both'),
    ('salary', '工资收入', 'income'),
    ('other-income', '其他收入', 'income'),
    ('other', '其他', 'both');
