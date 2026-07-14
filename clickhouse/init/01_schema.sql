CREATE DATABASE IF NOT EXISTS sales_analytics;

-- Products dimension (denormalized with vendor info)
CREATE TABLE IF NOT EXISTS sales_analytics.dim_products (
    product_id            UInt64,
    name                  String,
    price                 UInt64,
    stock                 Int32,
    sales_count_week      Int32,
    rating_average        Float32,
    rating_count          Int32,
    preparation_days      Int32,
    category_id           Int32,
    category_title        String,
    status_title          String,
    is_free_shipping      UInt8,
    is_available          UInt8,
    is_saleable           UInt8,
    vendor_id             UInt64,
    vendor_name           String,
    vendor_identifier     String,
    vendor_status_id      Int32,
    vendor_status_title   String,
    vendor_score          Float32,
    vendor_owner_id       UInt64,
    vendor_owner_city     String,
    vendor_province_id    Int32,
    vendor_city_id        Int32,
    vendor_has_delivery   UInt8,
    published             UInt8,
    updated_at            DateTime,
    _version              UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_version)
ORDER BY product_id;

-- Reviews fact table
CREATE TABLE IF NOT EXISTS sales_analytics.fact_reviews (
    review_id         String,
    product_id        UInt64,
    vendor_id         UInt64 DEFAULT 0,
    user_id           UInt64,
    star              UInt8,
    description       String,
    like_count        Int32,
    dislike_count     Int32,
    has_attachment    UInt8,
    is_public         UInt8,
    created_at        DateTime,
    created_hour      UInt8 MATERIALIZED toHour(created_at),
    created_day       Date MATERIALIZED toDate(created_at),
    updated_at        DateTime,
    _version          UInt64 DEFAULT 1
) ENGINE = ReplacingMergeTree(_version)
PARTITION BY toYYYYMM(created_at)
ORDER BY (product_id, created_at, review_id);

-- CDC audit mirror
CREATE TABLE IF NOT EXISTS sales_analytics.cdc_audit_mirror (
    audit_id    UInt64,
    table_name  String,
    operation   String,
    record_id   String,
    changed_at  DateTime,
    loaded_at   DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY audit_id;

-- ============================================================
-- DATA MARTS
-- ============================================================

CREATE TABLE IF NOT EXISTS sales_analytics.dm_top_vendors (
    vendor_id          UInt64,
    vendor_name        String,
    vendor_owner_city  String,
    vendor_province_id Int32,
    weekly_sales       Int64,
    rating_average     Float32,
    total_reviews      UInt64,
    computed_at        DateTime DEFAULT now()
) ENGINE = SummingMergeTree()
ORDER BY vendor_id;

CREATE TABLE IF NOT EXISTS sales_analytics.dm_free_shipping_analysis (
    product_id         UInt64,
    vendor_id          UInt64,
    preparation_days   Int32,
    is_free_shipping   UInt8,
    rating_average     Float32,
    sales_count_week   Int32,
    computed_at        DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (preparation_days, is_free_shipping);

CREATE TABLE IF NOT EXISTS sales_analytics.dm_trending_categories (
    category_id        Int32,
    category_title       String,
    monthly_reviews      UInt64,
    weekly_sales         Int64,
    month_start          Date,
    computed_at          DateTime DEFAULT now()
) ENGINE = SummingMergeTree()
ORDER BY (month_start, category_id);

CREATE TABLE IF NOT EXISTS sales_analytics.dm_review_engagement (
    review_id          String,
    star               UInt8,
    has_attachment     UInt8,
    like_count         Int64,
    description_length UInt32,
    created_day        Date,
    computed_at        DateTime DEFAULT now()
) ENGINE = SummingMergeTree()
ORDER BY (created_day, star, has_attachment);
