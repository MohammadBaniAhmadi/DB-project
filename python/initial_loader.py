"""
Initial data loader - loads BaSalam CSV files into PostgreSQL using Python only.
Supports chunked batch insert for large files (~2.4M products, ~3.4M reviews).
"""

import csv
import os
import sys
import time
from datetime import datetime

import psycopg
from psycopg import sql

from config import Config, get_postgres_connection

BATCH_SIZE = 5000

PRODUCT_COLUMNS = [
    "product_id", "name", "price", "stock", "sales_count_week", "rating_average",
    "rating_count", "preparation_days", "category_id", "category_title", "status_title",
    "is_free_shipping", "is_available", "is_saleable", "vendor_id", "vendor_name",
    "vendor_identifier", "vendor_status_id", "vendor_status_title", "vendor_score",
    "vendor_owner_id", "vendor_owner_city", "vendor_province_id", "vendor_city_id",
    "vendor_free_shipping_to_iran", "vendor_free_shipping_to_same_city",
    "vendor_has_delivery", "published",
]

REVIEW_COLUMNS = [
    "review_id", "product_id", "user_id", "star", "description",
    "like_count", "dislike_count", "attachments", "is_public", "is_post",
    "created_at", "updated_at",
]


def wait_for_postgres(cfg: Config, max_retries: int = 30):
    for i in range(max_retries):
        try:
            conn = get_postgres_connection(cfg)
            conn.close()
            print("PostgreSQL is ready.")
            return
        except psycopg.OperationalError:
            print(f"Waiting for PostgreSQL... ({i + 1}/{max_retries})")
            time.sleep(2)
    raise RuntimeError("PostgreSQL not available")


def parse_bool(val) -> bool | None:
    if val is None or val == "":
        return None
    return str(val).strip().lower() in ("true", "1", "yes", "t")


def parse_int(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def parse_bigint(val) -> int | None:
    if val is None or val == "":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def parse_float(val) -> float | None:
    if val is None or val == "":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def parse_ts(val) -> datetime | None:
    if val is None or val == "":
        return None
    try:
        return datetime.fromisoformat(str(val).replace("Z", ""))
    except ValueError:
        return None


def transform_product(row: dict) -> tuple:
    return (
        parse_bigint(row.get("_id")),
        row.get("name") or None,
        parse_bigint(row.get("price")),
        parse_int(row.get("stock")),
        parse_int(row.get("sales_count_week")),
        parse_float(row.get("rating_average")),
        parse_int(row.get("rating_count")),
        parse_int(row.get("preparationDays")),
        parse_int(row.get("categoryId")),
        row.get("categoryTitle") or None,
        row.get("status_title") or None,
        parse_bool(row.get("isFreeShipping")),
        parse_bool(row.get("IsAvailable")),
        parse_bool(row.get("IsSaleable")),
        parse_bigint(row.get("vendor_id")),
        row.get("vendor_name") or None,
        row.get("vendor_identifier") or None,
        parse_int(row.get("vendor_status_id")),
        row.get("vendor_status_title") or None,
        parse_float(row.get("vendor_score")),
        parse_bigint(row.get("vendor_owner_id")),
        row.get("vendor_owner_city") or None,
        parse_int(row.get("vendor_provinceId")),
        parse_int(row.get("vendor_cityId")),
        parse_bigint(row.get("vendor_freeShippingToIran")),
        parse_bigint(row.get("vendor_freeShippingToSameCity")),
        parse_bool(row.get("vendor_has_delivery")),
        parse_bool(row.get("published")),
    )


def transform_review(row: dict) -> tuple | None:
    product_id = parse_bigint(row.get("productId"))
    review_id = row.get("_id")
    if not product_id or not review_id:
        return None
    return (
        review_id,
        product_id,
        parse_bigint(row.get("user_id")),
        parse_int(row.get("star")),
        row.get("description") or None,
        parse_int(row.get("likeCount")) or 0,
        parse_int(row.get("dislikeCount")) or 0,
        row.get("attachments") or None,
        parse_bool(row.get("isPublic")),
        parse_bool(row.get("isPost")),
        parse_ts(row.get("createdAt")),
        parse_ts(row.get("updatedAt")),
    )


def insert_batch(conn, table: str, columns: list, rows: list):
    if not rows:
        return
    placeholders = sql.SQL(", ").join(sql.Placeholder() * len(columns))
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, columns)),
        placeholders,
    )
    with conn.cursor() as cur:
        cur.executemany(query, rows)
    conn.commit()


def load_products(conn, filepath: str, limit: int | None = None):
    print(f"Loading products from {filepath}...")
    total = 0
    skipped = 0
    batch = []
    start = time.time()

    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if limit and total + skipped >= limit:
                break
            product = transform_product(row)
            if product[0] is None:
                skipped += 1
                continue
            batch.append(product)
            if len(batch) >= BATCH_SIZE:
                insert_batch(conn, "products", PRODUCT_COLUMNS, batch)
                total += len(batch)
                batch = []
                if total % 100000 == 0:
                    elapsed = time.time() - start
                    print(f"  Products: {total:,} rows ({elapsed:.0f}s)")

    if batch:
        insert_batch(conn, "products", PRODUCT_COLUMNS, batch)
        total += len(batch)

    print(f"  Loaded {total:,} products (skipped {skipped}) in {time.time() - start:.0f}s")


def load_reviews(conn, filepath: str, limit: int | None = None):
    print(f"Loading reviews from {filepath}...")
    total = 0
    skipped = 0
    batch = []
    start = time.time()
    product_ids = set()

    with conn.cursor() as cur:
        cur.execute("SELECT product_id FROM products")
        product_ids = {r[0] for r in cur.fetchall()}
    print(f"  Valid product IDs in DB: {len(product_ids):,}")

    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if limit and total + skipped >= limit:
                break
            review = transform_review(row)
            if review is None or review[1] not in product_ids:
                skipped += 1
                continue
            batch.append(review)
            if len(batch) >= BATCH_SIZE:
                insert_batch(conn, "reviews", REVIEW_COLUMNS, batch)
                total += len(batch)
                batch = []
                if total % 100000 == 0:
                    elapsed = time.time() - start
                    print(f"  Reviews: {total:,} rows ({elapsed:.0f}s)")

    if batch:
        insert_batch(conn, "reviews", REVIEW_COLUMNS, batch)
        total += len(batch)

    print(f"  Loaded {total:,} reviews (skipped {skipped}) in {time.time() - start:.0f}s")


def main():
    cfg = Config()
    wait_for_postgres(cfg)

    products_path = os.path.join(cfg.data_dir, "raw", "products", "BaSalam.products.csv")
    reviews_path = os.path.join(cfg.data_dir, "raw", "reviews", "BaSalam.reviews.csv")

    if not os.path.exists(products_path):
        print(f"ERROR: {products_path} not found.")
        print("Extract download.zip into data/raw/ first.")
        sys.exit(1)

    limit = int(os.getenv("LOAD_LIMIT", "0")) or None

    conn = get_postgres_connection(cfg)
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE products DISABLE TRIGGER trg_products_audit")
            cur.execute("ALTER TABLE reviews DISABLE TRIGGER trg_reviews_audit")
        conn.commit()

        load_products(conn, products_path, limit=limit)

        if os.path.exists(reviews_path):
            load_reviews(conn, reviews_path, limit=limit)
        else:
            print(f"WARNING: {reviews_path} not found, skipping reviews.")

        with conn.cursor() as cur:
            cur.execute("ALTER TABLE products ENABLE TRIGGER trg_products_audit")
            cur.execute("ALTER TABLE reviews ENABLE TRIGGER trg_reviews_audit")
        conn.commit()

        print("Initial load complete.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
