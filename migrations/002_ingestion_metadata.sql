ALTER TABLE source_records ADD COLUMN parser_name TEXT NOT NULL DEFAULT '';

CREATE INDEX source_records_parser_retry_idx
    ON source_records (parser_name, state, uid);
