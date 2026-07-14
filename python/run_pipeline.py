"""
One-shot pipeline runner: initial load + full sync + data mart refresh.
"""

from incremental_loader import IncrementalLoader
from config import get_postgres_connection


def main():
    loader = IncrementalLoader()
    loader.connect_clickhouse()
    pg = get_postgres_connection()
    try:
        loader.full_initial_sync(pg)
        loader.refresh_data_marts()
        with pg.cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(audit_id), 0) FROM audit_log")
            max_audit = cur.fetchone()[0]
        loader.set_last_audit_id(pg, max_audit)
        print("Pipeline sync complete.")
    finally:
        pg.close()


if __name__ == "__main__":
    main()
