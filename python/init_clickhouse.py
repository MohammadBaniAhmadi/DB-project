"""
Initialize ClickHouse schema from SQL file.
"""

import os

from config import Config, get_clickhouse_client


def init_schema(cfg: Config | None = None):
    cfg = cfg or Config()
    schema_path = os.path.join(
        os.path.dirname(__file__), "..", "clickhouse", "init", "01_schema.sql"
    )

    client = get_clickhouse_client(cfg)
    with open(schema_path, encoding="utf-8") as f:
        sql = f.read()

    statements = [s.strip() for s in sql.split(";") if s.strip()]
    for stmt in statements:
        if stmt:
            client.command(stmt)
    print("ClickHouse schema initialized.")


if __name__ == "__main__":
    init_schema()
