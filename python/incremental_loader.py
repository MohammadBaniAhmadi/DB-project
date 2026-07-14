"""
Incremental loader: polls PostgreSQL audit_log and loads transformed data into ClickHouse.
"""

import json
import time
from datetime import datetime

from config import Config, get_clickhouse_client, get_postgres_connection

SYNC_BATCH = 10000


class IncrementalLoader:
    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or Config()
        self.ch = None

    def connect_clickhouse(self):
        for _ in range(30):
            try:
                self.ch = get_clickhouse_client(self.cfg)
                self.ch.command("SELECT 1")
                print("ClickHouse is ready.")
                self._ensure_schema()
                return
            except Exception:
                print("Waiting for ClickHouse...")
                time.sleep(2)
        raise RuntimeError("ClickHouse not available")

    def _ensure_schema(self):
        import os
        schema_path = os.path.join(os.path.dirname(__file__), "..", "clickhouse", "init", "01_schema.sql")
        if not os.path.exists(schema_path):
            return
        with open(schema_path, encoding="utf-8") as f:
            for stmt in f.read().split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        self.ch.command(stmt)
                    except Exception:
                        pass

    def get_last_audit_id(self, conn) -> int:
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM loader_state WHERE key = 'last_audit_id'")
            row = cur.fetchone()
            return row[0] if row else 0

    def set_last_audit_id(self, conn, audit_id: int):
        with conn.cursor() as cur:
            cur.execute("UPDATE loader_state SET value = %s WHERE key = 'last_audit_id'", (audit_id,))
        conn.commit()

    def fetch_new_audit_records(self, conn, last_id: int) -> list:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT audit_id, table_name, operation, record_id, old_data, new_data, changed_at
                   FROM audit_log WHERE audit_id > %s AND processed = FALSE
                   ORDER BY audit_id LIMIT %s""",
                (last_id, self.cfg.batch_size),
            )
            return cur.fetchall()

    def mark_processed(self, conn, audit_ids: list):
        if not audit_ids:
            return
        with conn.cursor() as cur:
            cur.execute("UPDATE audit_log SET processed = TRUE WHERE audit_id = ANY(%s)", (audit_ids,))
        conn.commit()

    def _bool(self, val) -> int:
        return 1 if val in (True, "true", "t", 1, "1") else 0

    def _has_attachment(self, attachments) -> int:
        if not attachments:
            return 0
        text = str(attachments)
        return 1 if "photos" in text and "[]" not in text.split("photos")[1][:20] else (
            1 if "http" in text else 0
        )

    def _parse_ts(self, val) -> datetime:
        if val is None:
            return datetime(2000, 1, 1)
        if isinstance(val, datetime):
            return val
        return datetime.fromisoformat(str(val).replace("Z", "").split("+")[0])

    def transform_product(self, data: dict) -> dict:
        return {
            "product_id": int(data["product_id"]),
            "name": data.get("name") or "",
            "price": int(data.get("price") or 0),
            "stock": int(data.get("stock") or 0),
            "sales_count_week": int(data.get("sales_count_week") or 0),
            "rating_average": float(data.get("rating_average") or 0),
            "rating_count": int(data.get("rating_count") or 0),
            "preparation_days": int(data.get("preparation_days") or 1),
            "category_id": int(data.get("category_id") or 0),
            "category_title": data.get("category_title") or "",
            "status_title": data.get("status_title") or "",
            "is_free_shipping": self._bool(data.get("is_free_shipping")),
            "is_available": self._bool(data.get("is_available")),
            "is_saleable": self._bool(data.get("is_saleable")),
            "vendor_id": int(data.get("vendor_id") or 0),
            "vendor_name": data.get("vendor_name") or "",
            "vendor_identifier": data.get("vendor_identifier") or "",
            "vendor_status_id": int(data.get("vendor_status_id") or 0),
            "vendor_status_title": data.get("vendor_status_title") or "",
            "vendor_score": float(data.get("vendor_score") or 0),
            "vendor_owner_id": int(data.get("vendor_owner_id") or 0),
            "vendor_owner_city": data.get("vendor_owner_city") or "",
            "vendor_province_id": int(data.get("vendor_province_id") or 0),
            "vendor_city_id": int(data.get("vendor_city_id") or 0),
            "vendor_has_delivery": self._bool(data.get("vendor_has_delivery")),
            "published": self._bool(data.get("published")),
            "updated_at": self._parse_ts(data.get("updated_at")),
            "_version": int(datetime.now().timestamp() * 1000),
        }

    def transform_review(self, data: dict, vendor_map: dict) -> dict:
        product_id = int(data["product_id"])
        return {
            "review_id": str(data["review_id"]),
            "product_id": product_id,
            "vendor_id": vendor_map.get(product_id, 0),
            "user_id": int(data.get("user_id") or 0),
            "star": int(data.get("star") or 0),
            "description": data.get("description") or "",
            "like_count": int(data.get("like_count") or 0),
            "dislike_count": int(data.get("dislike_count") or 0),
            "has_attachment": self._has_attachment(data.get("attachments")),
            "is_public": self._bool(data.get("is_public")),
            "created_at": self._parse_ts(data.get("created_at")),
            "updated_at": self._parse_ts(data.get("updated_at")),
            "_version": int(datetime.now().timestamp() * 1000),
        }

    def load_vendor_map(self, conn) -> dict:
        with conn.cursor() as cur:
            cur.execute("SELECT product_id, vendor_id FROM products")
            return {r[0]: r[1] for r in cur.fetchall()}

    def insert_rows(self, table: str, rows: list):
        if not rows:
            return
        columns = list(rows[0].keys())
        data = [[row[c] for c in columns] for row in rows]
        self.ch.insert(table, data, column_names=columns)

    def process_batch(self, conn, records: list):
        vendor_map = self.load_vendor_map(conn)
        products, reviews, audit_mirror = [], [], []

        for audit_id, table_name, operation, record_id, old_data, new_data, changed_at in records:
            data = new_data if new_data else old_data
            if isinstance(data, str):
                data = json.loads(data)

            audit_mirror.append({
                "audit_id": audit_id, "table_name": table_name,
                "operation": operation, "record_id": str(record_id),
                "changed_at": changed_at,
            })

            if table_name == "products" and operation in ("I", "U"):
                products.append(self.transform_product(data))
            elif table_name == "reviews" and operation in ("I", "U"):
                reviews.append(self.transform_review(data, vendor_map))

        self.insert_rows("dim_products", products)
        self.insert_rows("fact_reviews", reviews)
        self.insert_rows("cdc_audit_mirror", audit_mirror)

        audit_ids = [r[0] for r in records]
        self.mark_processed(conn, audit_ids)
        self.set_last_audit_id(conn, max(audit_ids))
        print(f"  Processed {len(records)} audit records")

    def _sync_table(self, conn, table: str, columns: list, transform_fn, ch_table: str, *extra_args):
        offset = 0
        total = 0
        while True:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {', '.join(columns)} FROM {table} ORDER BY 1 LIMIT %s OFFSET %s",
                    (SYNC_BATCH, offset),
                )
                rows = cur.fetchall()
            if not rows:
                break
            batch = [transform_fn(dict(zip(columns, row)), *extra_args) for row in rows]
            self.insert_rows(ch_table, batch)
            total += len(batch)
            offset += SYNC_BATCH
            if total % 100000 == 0:
                print(f"  {table}: {total:,} synced")
        print(f"  Total {table}: {total:,}")

    def full_initial_sync(self, conn):
        print("Running full initial sync to ClickHouse...")
        vendor_map = self.load_vendor_map(conn)

        product_cols = [
            "product_id", "name", "price", "stock", "sales_count_week", "rating_average",
            "rating_count", "preparation_days", "category_id", "category_title", "status_title",
            "is_free_shipping", "is_available", "is_saleable", "vendor_id", "vendor_name",
            "vendor_identifier", "vendor_status_id", "vendor_status_title", "vendor_score",
            "vendor_owner_id", "vendor_owner_city", "vendor_province_id", "vendor_city_id",
            "vendor_has_delivery", "published", "updated_at",
        ]
        self._sync_table(conn, "products", product_cols, self.transform_product, "dim_products")

        review_cols = [
            "review_id", "product_id", "user_id", "star", "description",
            "like_count", "dislike_count", "attachments", "is_public", "created_at", "updated_at",
        ]
        self._sync_table(conn, "reviews", review_cols, self.transform_review, "fact_reviews", vendor_map)
        print("Full initial sync complete.")

    def refresh_data_marts(self):
        print("Refreshing data marts...")

        self.ch.command("TRUNCATE TABLE IF EXISTS dm_top_vendors")
        self.ch.command("""
            INSERT INTO dm_top_vendors
            SELECT
                vendor_id,
                any(vendor_name) AS vendor_name,
                any(vendor_owner_city) AS vendor_owner_city,
                any(vendor_province_id) AS vendor_province_id,
                sum(sales_count_week) AS weekly_sales,
                avg(rating_average) AS rating_average,
                0 AS total_reviews,
                now()
            FROM dim_products FINAL
            GROUP BY vendor_id
        """)

        self.ch.command("TRUNCATE TABLE IF EXISTS dm_free_shipping_analysis")
        self.ch.command("""
            INSERT INTO dm_free_shipping_analysis
            SELECT product_id, vendor_id, preparation_days, is_free_shipping,
                   rating_average, sales_count_week, now()
            FROM dim_products FINAL
        """)

        self.ch.command("TRUNCATE TABLE IF EXISTS dm_trending_categories")
        self.ch.command("""
            INSERT INTO dm_trending_categories
            SELECT
                p.category_id,
                any(p.category_title) AS category_title,
                count() AS monthly_reviews,
                sum(p.sales_count_week) AS weekly_sales,
                toStartOfMonth(r.created_at) AS month_start,
                now()
            FROM dim_products p FINAL
            JOIN fact_reviews r ON r.product_id = p.product_id
            WHERE r.created_at >= today() - 30
            GROUP BY p.category_id, month_start
        """)

        self.ch.command("TRUNCATE TABLE IF EXISTS dm_review_engagement")
        self.ch.command("""
            INSERT INTO dm_review_engagement
            SELECT review_id, star, has_attachment, like_count,
                   length(description), toDate(created_at), now()
            FROM fact_reviews FINAL
        """)

        print("Data marts refreshed.")

    def run(self):
        self.connect_clickhouse()
        pg_conn = get_postgres_connection(self.cfg)
        try:
            last_id = self.get_last_audit_id(pg_conn)
            if last_id == 0:
                self.full_initial_sync(pg_conn)
                self.refresh_data_marts()
                with pg_conn.cursor() as cur:
                    cur.execute("SELECT COALESCE(MAX(audit_id), 0) FROM audit_log")
                    self.set_last_audit_id(pg_conn, cur.fetchone()[0])

            print(f"Starting incremental loader (poll={self.cfg.poll_interval}s)...")
            cycle = 0
            while True:
                last_id = self.get_last_audit_id(pg_conn)
                records = self.fetch_new_audit_records(pg_conn, last_id)
                if records:
                    self.process_batch(pg_conn, records)
                    if cycle % 5 == 0:
                        self.refresh_data_marts()
                else:
                    print(f"[{datetime.now():%H:%M:%S}] No new audit records.")
                cycle += 1
                time.sleep(self.cfg.poll_interval)
        finally:
            pg_conn.close()


if __name__ == "__main__":
    IncrementalLoader().run()
