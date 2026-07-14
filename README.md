# پروژه ۵: طراحی خط لوله داده از OLTP به OLAP

پروژه درس **طراحی پایگاه داده‌ها** — انتقال افزایشی داده باسلام (BaSalam) از PostgreSQL به ClickHouse

## داده‌های پروژه

فایل `download.zip` شامل:
- `BaSalam.products.csv` (~۲.۴ میلیون محصول)
- `BaSalam.reviews.csv` (~۳.۴ میلیون نظر)
- `docker-compose-sample.yml` (نمونه مرجع)

**راه‌اندازی داده:**
```bash
# فایل download.zip را در data/raw/ استخراج کنید
Expand-Archive download.zip -DestinationPath data/raw
Expand-Archive data/raw/BaSalam.products.csv.zip -DestinationPath data/raw/products
Expand-Archive data/raw/BaSalam.reviews.csv.zip -DestinationPath data/raw/reviews
```

## معماری

```
PostgreSQL (sales)  →  CDC (audit_log + Trigger)  →  Python ETL  →  ClickHouse (sales_analytics)
```

## پیش‌نیازها

- Docker و Docker Compose
- Python 3.11+ با `psycopg[binary]` و `clickhouse-connect`

## راه‌اندازی

```bash
# ۱. اجرای دیتابیس‌ها
docker compose up -d postgres clickhouse

# ۲. نصب وابستگی‌ها
cd python && pip install -r requirements.txt

# ۳. بارگذاری اولیه (فقط Python)
python initial_loader.py

# ۴. همگام‌سازی با ClickHouse
python run_pipeline.py

# ۵. شبیه‌سازی تغییرات (۱۵ دقیقه)
python data_simulator.py 15 30

# ۶. پردازش CDC و بنچمارک
python process_cdc_once.py
python benchmark_queries.py
```

### بارگذاری محدود (برای تست سریع)

```bash
set LOAD_LIMIT=50000
python initial_loader.py
```

### مهاجرت از اسکیمای قبلی

اگر قبلاً داده مصنوعی بارگذاری کرده‌اید، دیتابیس را ریست کنید:

```bash
docker compose down -v
docker compose up -d postgres clickhouse
```

یا فایل `postgres/migrate_basalam.sql` را اجرا کنید.

## ساختار پروژه

```
├── docker-compose.yml
├── postgres/init/          # Schema OLTP + CDC Triggers
├── clickhouse/init/        # Schema OLAP + Data Marts
├── data/raw/               # داده‌های BaSalam (از download.zip)
├── python/
│   ├── initial_loader.py   # بارگذاری CSV → PostgreSQL
│   ├── incremental_loader.py
│   ├── data_simulator.py
│   ├── run_pipeline.py
│   ├── process_cdc_once.py
│   └── benchmark_queries.py
├── queries/                # ۱۰ کوئری تحلیلی + Data Marts
└── docs/REPORT.md          # گزارش کامل فارسی
```

## پورت‌ها

| سرویس | پورت |
|--------|------|
| PostgreSQL | 5433 |
| ClickHouse HTTP | 8123 |

## تحویل

فایل ZIP شامل `docs/REPORT.md` و اسکریپت‌های `python/`
