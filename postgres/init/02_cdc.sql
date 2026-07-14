-- CDC Layer: Audit Table + Triggers

CREATE TABLE audit_log (
    audit_id      BIGSERIAL PRIMARY KEY,
    table_name    VARCHAR(100) NOT NULL,
    operation     CHAR(1) NOT NULL CHECK (operation IN ('I', 'U', 'D')),
    record_id     VARCHAR(100) NOT NULL,
    old_data      JSONB,
    new_data      JSONB,
    changed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed     BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_audit_unprocessed ON audit_log(processed, audit_id) WHERE processed = FALSE;
CREATE INDEX idx_audit_table ON audit_log(table_name);

CREATE OR REPLACE FUNCTION products_audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, operation, record_id, new_data)
        VALUES ('products', 'I', NEW.product_id::TEXT, row_to_json(NEW)::jsonb);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, operation, record_id, old_data, new_data)
        VALUES ('products', 'U', NEW.product_id::TEXT, row_to_json(OLD)::jsonb, row_to_json(NEW)::jsonb);
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION reviews_audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO audit_log (table_name, operation, record_id, new_data)
        VALUES ('reviews', 'I', NEW.review_id, row_to_json(NEW)::jsonb);
        RETURN NEW;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_log (table_name, operation, record_id, old_data, new_data)
        VALUES ('reviews', 'U', NEW.review_id, row_to_json(OLD)::jsonb, row_to_json(NEW)::jsonb);
        RETURN NEW;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_products_audit
    AFTER INSERT OR UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION products_audit_trigger_func();

CREATE TRIGGER trg_reviews_audit
    AFTER INSERT OR UPDATE ON reviews
    FOR EACH ROW EXECUTE FUNCTION reviews_audit_trigger_func();

CREATE TABLE loader_state (
    key   VARCHAR(50) PRIMARY KEY,
    value BIGINT NOT NULL DEFAULT 0
);

INSERT INTO loader_state (key, value) VALUES ('last_audit_id', 0);
