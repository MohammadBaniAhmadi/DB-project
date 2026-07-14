-- OLTP Schema for BaSalam Sales Data
-- Database: sales

-- Products (denormalized with vendor info from BaSalam.products.csv)
CREATE TABLE products (
    product_id           BIGINT PRIMARY KEY,
    name                 TEXT,
    price                BIGINT,
    stock                INTEGER DEFAULT 0,
    sales_count_week     INTEGER DEFAULT 0,
    rating_average       NUMERIC(4,2) DEFAULT 0,
    rating_count         INTEGER DEFAULT 0,
    preparation_days     INTEGER DEFAULT 1,
    category_id          INTEGER,
    category_title       VARCHAR(200),
    status_title         VARCHAR(100),
    is_free_shipping     BOOLEAN DEFAULT FALSE,
    is_available         BOOLEAN DEFAULT TRUE,
    is_saleable          BOOLEAN DEFAULT TRUE,
    vendor_id            BIGINT,
    vendor_name          TEXT,
    vendor_identifier    VARCHAR(100),
    vendor_status_id     INTEGER,
    vendor_status_title  VARCHAR(100),
    vendor_score         NUMERIC(4,2) DEFAULT 0,
    vendor_owner_id      BIGINT,
    vendor_owner_city    VARCHAR(100),
    vendor_province_id   INTEGER,
    vendor_city_id       INTEGER,
    vendor_free_shipping_to_iran      BIGINT,
    vendor_free_shipping_to_same_city BIGINT,
    vendor_has_delivery  BOOLEAN,
    published            BOOLEAN,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Reviews (from BaSalam.reviews.csv)
CREATE TABLE reviews (
    review_id     VARCHAR(50) PRIMARY KEY,
    product_id    BIGINT NOT NULL REFERENCES products(product_id),
    user_id       BIGINT,
    star          SMALLINT CHECK (star BETWEEN 1 AND 5),
    description   TEXT,
    like_count    INTEGER DEFAULT 0,
    dislike_count INTEGER DEFAULT 0,
    attachments   TEXT,
    is_public     BOOLEAN DEFAULT TRUE,
    is_post       BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP,
    updated_at    TIMESTAMP
);

-- Indexes for analytical queries
CREATE INDEX idx_products_vendor ON products(vendor_id);
CREATE INDEX idx_products_vendor_province ON products(vendor_province_id);
CREATE INDEX idx_products_category ON products(category_id);
CREATE INDEX idx_products_stock ON products(stock);
CREATE INDEX idx_products_sales_week ON products(sales_count_week);
CREATE INDEX idx_reviews_product ON reviews(product_id);
CREATE INDEX idx_reviews_user ON reviews(user_id);
CREATE INDEX idx_reviews_star ON reviews(star);
CREATE INDEX idx_reviews_created ON reviews(created_at);
CREATE INDEX idx_reviews_public ON reviews(is_public);
