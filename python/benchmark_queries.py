"""Benchmark: PostgreSQL vs ClickHouse query performance."""

import time

from config import Config, get_clickhouse_client, get_postgres_connection

BENCHMARKS = [
    ("Q2: Avg rating per hour", {
        "postgres": "SELECT EXTRACT(HOUR FROM created_at), AVG(star), COUNT(*) FROM reviews GROUP BY 1 ORDER BY 1",
        "clickhouse": "SELECT toHour(created_at), avg(star), count() FROM fact_reviews FINAL GROUP BY 1 ORDER BY 1",
    }),
    ("Q6: Top provinces", {
        "postgres": """
            SELECT vendor_province_id, AVG(vendor_score), SUM(sales_count_week)
            FROM products GROUP BY vendor_province_id ORDER BY 2 DESC LIMIT 10
        """,
        "clickhouse": """
            SELECT vendor_province_id, avg(vendor_score), sum(sales_count_week)
            FROM dim_products FINAL GROUP BY vendor_province_id ORDER BY 2 DESC LIMIT 10
        """,
    }),
    ("Q7: Word frequency star=1", {
        "postgres": """
            WITH words AS (SELECT unnest(string_to_array(description,' ')) AS word FROM reviews WHERE star=1)
            SELECT word, COUNT(*) FROM words WHERE length(word)>2 GROUP BY word ORDER BY 2 DESC LIMIT 10
        """,
        "clickhouse": """
            SELECT arrayJoin(splitByChar(' ', description)) AS word, count()
            FROM fact_reviews FINAL WHERE star=1 AND length(word)>2 GROUP BY word ORDER BY 2 DESC LIMIT 10
        """,
    }),
    ("Q9: Positive review users", {
        "postgres": """
            SELECT user_id, COUNT(*) FROM reviews
            WHERE description LIKE '%عالی%' OR description LIKE '%خوب%'
            GROUP BY user_id ORDER BY 2 DESC LIMIT 10
        """,
        "clickhouse": """
            SELECT user_id, count() FROM fact_reviews FINAL
            WHERE description LIKE '%عالی%' OR description LIKE '%خوب%'
            GROUP BY user_id ORDER BY 2 DESC LIMIT 10
        """,
    }),
]


def benchmark_postgres(conn, sql, runs=3):
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(sql)
            cur.fetchall()
        times.append(time.perf_counter() - start)
    return min(times) * 1000


def benchmark_clickhouse(ch, sql, runs=3):
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        ch.query(sql)
        times.append(time.perf_counter() - start)
    return min(times) * 1000


def main():
    cfg = Config()
    pg = get_postgres_connection(cfg)
    ch = get_clickhouse_client(cfg)

    print("=" * 70)
    print("Benchmark: PostgreSQL (OLTP) vs ClickHouse (OLAP) - BaSalam Data")
    print("=" * 70)
    print(f"{'Query':<35} {'PostgreSQL (ms)':>15} {'ClickHouse (ms)':>15} {'Ratio':>10}")
    print("-" * 70)

    for name, q in BENCHMARKS:
        pg_ms = benchmark_postgres(pg, q["postgres"])
        ch_ms = benchmark_clickhouse(ch, q["clickhouse"])
        ratio = pg_ms / ch_ms if ch_ms > 0 else 0
        print(f"{name:<35} {pg_ms:>15.2f} {ch_ms:>15.2f} {ratio:>9.1f}x")

    print("=" * 70)
    pg.close()


if __name__ == "__main__":
    main()
