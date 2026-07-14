"""
Data simulator - periodically modifies BaSalam data to generate CDC events.
"""

import random
import sys
import time
from datetime import datetime

from config import Config, get_postgres_connection

POSITIVE_WORDS = ["عالی", "خوشمزه", "خوب", "فوق‌العاده"]
DELIVERY_WORDS = ["ارسال", "دیر"]


def simulate_review_insert(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT product_id FROM products ORDER BY RANDOM() LIMIT 1")
        product_id = cur.fetchone()[0]
        cur.execute("SELECT user_id FROM reviews ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
        user_id = row[0] if row else random.randint(1, 99999999)
        star = random.randint(1, 5)
        desc = " ".join(random.sample(POSITIVE_WORDS + DELIVERY_WORDS, 3))
        review_id = f"sim{int(datetime.now().timestamp() * 1000)}{random.randint(1000, 9999)}"
        cur.execute(
            """INSERT INTO reviews (review_id, product_id, user_id, star, description,
               like_count, attachments, is_public, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, 0, %s, TRUE, %s, %s)""",
            (review_id, product_id, user_id, star, desc,
             "{'photos': [], 'video': None}", datetime.now(), datetime.now()),
        )
    conn.commit()
    print(f"[{datetime.now():%H:%M:%S}] Inserted review {review_id} (star={star})")


def simulate_review_like(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT review_id, like_count FROM reviews ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE reviews SET like_count = %s, updated_at = %s WHERE review_id = %s",
                (row[1] + 1, datetime.now(), row[0]),
            )
            conn.commit()
            print(f"[{datetime.now():%H:%M:%S}] likeCount++ on review {row[0]}")


def simulate_product_stock(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT product_id, stock FROM products ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
        if row:
            new_stock = max(0, row[1] + random.randint(-10, 20))
            is_saleable = new_stock > 0
            cur.execute(
                """UPDATE products SET stock = %s, is_saleable = %s,
                   is_available = %s, updated_at = %s WHERE product_id = %s""",
                (new_stock, is_saleable, new_stock > 0, datetime.now(), row[0]),
            )
            conn.commit()
            print(f"[{datetime.now():%H:%M:%S}] product {row[0]} stock={new_stock}")


def simulate_vendor_score(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT product_id, vendor_score FROM products ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
        if row:
            new_score = round(min(5.0, max(0, float(row[1] or 0) + random.uniform(-0.5, 0.5))), 2)
            cur.execute(
                "UPDATE products SET vendor_score = %s, updated_at = %s WHERE product_id = %s",
                (new_score, datetime.now(), row[0]),
            )
            conn.commit()
            print(f"[{datetime.now():%H:%M:%S}] vendor_score={new_score} on product {row[0]}")


def simulate_sales_count(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT product_id, sales_count_week FROM products ORDER BY RANDOM() LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE products SET sales_count_week = %s, updated_at = %s WHERE product_id = %s",
                (row[1] + random.randint(1, 5), datetime.now(), row[0]),
            )
            conn.commit()
            print(f"[{datetime.now():%H:%M:%S}] sales_count_week updated on product {row[0]}")


ACTIONS = [simulate_review_insert, simulate_review_like, simulate_product_stock,
           simulate_vendor_score, simulate_sales_count]


def main():
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    cfg = Config()
    conn = get_postgres_connection(cfg)
    end_time = time.time() + duration * 60
    print(f"Simulating changes for {duration} min (interval={interval}s)...")
    try:
        while time.time() < end_time:
            try:
                random.choice(ACTIONS)(conn)
            except Exception as e:
                print(f"  Error: {e}")
                conn.rollback()
            time.sleep(interval)
    finally:
        conn.close()
        print("Simulation finished.")


if __name__ == "__main__":
    main()
