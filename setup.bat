@echo off
echo === BaSalam OLTP to OLAP Pipeline ===

echo [1/6] Starting Docker...
docker compose up -d postgres clickhouse
timeout /t 10 /nobreak > nul

echo [2/6] Checking data files...
if not exist "data\raw\products\BaSalam.products.csv" (
    echo ERROR: Extract download.zip first. See README.md
    exit /b 1
)

echo [3/6] Installing Python deps...
cd python
pip install -r requirements.txt -q

echo [4/6] Loading data into PostgreSQL...
python initial_loader.py

echo [5/6] Syncing to ClickHouse...
python run_pipeline.py

echo [6/6] Running benchmark...
python benchmark_queries.py

echo === Done! See docs/REPORT.md ===
