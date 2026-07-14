-- Migration script: reset schema for BaSalam data
-- Run manually when upgrading from synthetic data schema:
--   docker exec -i sales_postgres psql -U postgres -d sales < postgres/migrate_basalam.sql

DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS loader_state CASCADE;
DROP TABLE IF EXISTS vendor_weekly_sales CASCADE;
DROP TABLE IF EXISTS vendors CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS provinces CASCADE;
DROP TABLE IF EXISTS vendor_statuses CASCADE;

\i /docker-entrypoint-initdb.d/01_schema.sql
\i /docker-entrypoint-initdb.d/02_cdc.sql
