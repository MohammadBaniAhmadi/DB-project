"""Process pending CDC audit records once (no polling loop)."""

from incremental_loader import IncrementalLoader
from config import get_postgres_connection


def main():
    loader = IncrementalLoader()
    loader.connect_clickhouse()
    pg = get_postgres_connection()
    try:
        last_id = loader.get_last_audit_id(pg)
        records = loader.fetch_new_audit_records(pg, last_id)
        if records:
            loader.process_batch(pg, records)
            loader.refresh_data_marts()
            print(f"Processed {len(records)} CDC records.")
        else:
            print("No pending CDC records.")
    finally:
        pg.close()


if __name__ == "__main__":
    main()
