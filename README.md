# Project 5: Designing a Data Pipeline from OLTP to OLAP

**Database Design** course project — Incremental transfer of BaSalam data from PostgreSQL to ClickHouse

## Project Data

The `download.zip` (download link is in download_link.txt) file contains:

- `BaSalam.products.csv` (~2.4 million products)
- `BaSalam.reviews.csv` (~3.4 million reviews)
- `docker-compose-sample.yml` (reference sample)

**Data setup:**

```powershell
# Extract download.zip into data/raw/
Expand-Archive download.zip -DestinationPath data/raw
Expand-Archive data/raw/BaSalam.products.csv.zip -DestinationPath data/raw/products
Expand-Archive data/raw/BaSalam.reviews.csv.zip -DestinationPath data/raw/reviews
```

## Architecture

```text
PostgreSQL (sales)  →  CDC (audit_log + Trigger)  →  Python ETL  →  ClickHouse (sales_analytics)
```

## Prerequisites

- Docker and Docker Compose
- Python 3.11+ with `psycopg[binary]` and `clickhouse-connect`

## Setup and Execution

```bash
# 1. Start the databases
docker compose up -d postgres clickhouse

# 2. Install the dependencies
cd python && pip install -r requirements.txt

# 3. Perform the initial data load (Python only)
python initial_loader.py

# 4. Synchronize the data with ClickHouse
python run_pipeline.py

# 5. Simulate data changes for 15 minutes
python data_simulator.py 15 30

# 6. Process CDC events and run the benchmarks
python process_cdc_once.py
python benchmark_queries.py
```

### Limited Data Loading for Quick Testing

```bash
set LOAD_LIMIT=50000
python initial_loader.py
```

### Migrating from the Previous Schema

If you have previously loaded synthetic data, reset the databases:

```bash
docker compose down -v
docker compose up -d postgres clickhouse
```

Alternatively, execute the `postgres/migrate_basalam.sql` script.

## Project Structure

```text
├── docker-compose.yml
├── postgres/init/          # OLTP schema and CDC triggers
├── clickhouse/init/        # OLAP schema and data marts
├── data/raw/               # BaSalam data extracted from download.zip
├── python/
│   ├── initial_loader.py   # Load CSV data into PostgreSQL
│   ├── incremental_loader.py
│   ├── data_simulator.py
│   ├── run_pipeline.py
│   ├── process_cdc_once.py
│   └── benchmark_queries.py
├── queries/                # 10 analytical queries and data marts
└── docs/REPORT.md          # Complete project report
```

## Ports

| Service | Port |
|---|---:|
| PostgreSQL | 5433 |
| ClickHouse HTTP | 8123 |