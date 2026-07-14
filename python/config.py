"""Shared configuration and database connections."""

import os
from dataclasses import dataclass


@dataclass
class Config:
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5433"))
    postgres_db: str = os.getenv("POSTGRES_DB", "sales")
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    clickhouse_host: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    clickhouse_port: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    clickhouse_db: str = os.getenv("CLICKHOUSE_DB", "sales_analytics")
    clickhouse_user: str = os.getenv("CLICKHOUSE_USER", "default")
    clickhouse_password: str = os.getenv("CLICKHOUSE_PASSWORD", "clickhouse")
    data_dir: str = os.getenv("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
    poll_interval: int = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
    batch_size: int = int(os.getenv("BATCH_SIZE", "500"))


def get_postgres_connection(cfg: Config | None = None):
    import psycopg
    cfg = cfg or Config()
    return psycopg.connect(
        host=cfg.postgres_host,
        port=cfg.postgres_port,
        dbname=cfg.postgres_db,
        user=cfg.postgres_user,
        password=cfg.postgres_password,
    )


def get_clickhouse_client(cfg: Config | None = None):
    import clickhouse_connect
    cfg = cfg or Config()
    return clickhouse_connect.get_client(
        host=cfg.clickhouse_host,
        port=cfg.clickhouse_port,
        username=cfg.clickhouse_user,
        password=cfg.clickhouse_password,
        database=cfg.clickhouse_db,
    )
