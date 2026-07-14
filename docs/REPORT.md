# گزارش پروژه ۵: طراحی خط لوله داده از OLTP به OLAP

**درس:** طراحی پایگاه داده‌ها  
**استاد:** دکتر مریم رمضانی  
**نیمسال:** بهار ۱۴۰۵

---

## فهرست مطالب

1. [مقدمه و هدف پروژه](#۱-مقدمه-و-هدف-پروژه)
2. [معماری سیستم](#۲-معماری-سیستم)
3. [مراحل پیاده‌سازی](#۳-مراحل-پیاده‌سازی)
4. [نتایج اجرای کوئری‌ها](#۴-نتایج-اجرای-کوئری‌ها)
5. [پاسخ سؤالات تحلیلی](#۵-پاسخ-سؤالات-تحلیلی)
6. [جمع‌بندی](#۶-جمع‌بندی)

---

## ۱. مقدمه و هدف پروژه

هدف این پروژه طراحی و پیاده‌سازی یک **خط لوله داده افزایشی (Incremental Data Pipeline)** برای انتقال داده‌های تراکنشی فروش از یک پایگاه داده عملیاتی (OLTP) به یک پایگاه داده تحلیلی (OLAP) است.

تمرکز اصلی پروژه بر سه مفهوم کلیدی است:
- **CDC (Change Data Capture):** شناسایی تغییرات داده با Trigger و جدول Audit
- **Incremental Loading:** بارگذاری فقط رکوردهای جدید/تغییریافته
- **بهینه‌سازی کوئری‌های تحلیلی:** طراحی ساختار ClickHouse برای پاسخ سریع

---

## ۲. معماری سیستم

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   PostgreSQL    │────▶│  Audit Log   │────▶│  Python Loader  │────▶│   ClickHouse    │
│   (OLTP/sales)  │     │  + Triggers  │     │  (ETL/CDC)      │     │   (OLAP)        │
└─────────────────┘     └──────────────┘     └─────────────────┘     └─────────────────┘
       ▲                                              │
       │                                              ▼
┌─────────────────┐                          ┌─────────────────┐
│ Data Simulator  │                          │   Data Marts    │
│ (تغییرات دوره‌ای)│                          │  (پیش‌محاسبه)    │
└─────────────────┘                          └─────────────────┘
```

### اجزای اصلی

| لایه | فناوری | نقش |
|------|---------|-----|
| منبع OLTP | PostgreSQL 16 | ذخیره داده‌های تراکنشی (فروشگاه آنلاین) |
| CDC | Trigger + audit_log | ثبت INSERT/UPDATE در جدول Audit |
| ETL | Python 3.11 | استخراج، تبدیل و بارگذاری افزایشی |
| مقصد OLAP | ClickHouse 24.3 | ذخیره‌سازی ستونی و کوئری‌های تحلیلی |
| Data Mart | ClickHouse Tables | پیش‌محاسبه نتایج پرتکرار |

### طراحی Schema

**PostgreSQL (مطابق داده BaSalam):**
- `products` — ۲۸ فیلد شامل اطلاعات محصول و غرفه (denormalized)
- `reviews` — نظرات با review_id از نوع VARCHAR (ObjectId)

**ClickHouse (Star Schema ساده‌شده):**
- `dim_products` — ابعاد محصول+غرفه
- `fact_reviews` — واقعیت نظرات با پارتیشن ماهانه

**چرا ClickHouse بهینه‌تر است؟**
- ذخیره‌سازی **ستونی (Columnar):** فقط ستون‌های مورد نیاز خوانده می‌شوند
- **ReplacingMergeTree:** مدیریت UPDATE با نگه‌داری آخرین نسخه
- **Partitioning:** پارتیشن‌بندی `fact_reviews` بر اساس ماه
- **Materialized Columns:** محاسبه `created_hour`, `is_saleable` در زمان INSERT

---

## ۳. مراحل پیاده‌سازی

### مرحله ۰: راه‌اندازی Docker

فایل `docker-compose.yml` سه سرویس را تعریف می‌کند:
1. **postgres** — پایگاه داده مبدأ
2. **clickhouse** — پایگاه داده مقصد
3. **python-app** — بارگذار افزایشی (اجرای مداوم)

### مرحله ۱: بارگذاری اولیه PostgreSQL

داده‌های واقعی **باسلام (BaSalam)** از فایل `download.zip` استفاده می‌شوند:
- `BaSalam.products.csv` — ۲,۴۱۱,۳۵۸ محصول (شامل اطلاعات غرفه denormalized)
- `BaSalam.reviews.csv` — ۳,۳۹۳,۵۷۵ نظر

اسکریپت `initial_loader.py` با **batch insert** (۵۰۰۰ رکورد) و **فقط Python** داده‌ها را بارگذاری می‌کند.

**فیلدهای کلیدی مطابق PDF:**
| PDF | ستون CSV | ستون DB |
|-----|----------|---------|
| vendor_name | vendor_name | vendor_name |
| vendor_score | vendor_score | vendor_score |
| vendor_status_title | vendor_status_title | vendor_status_title |
| vendor_owner_id | vendor_owner_id | vendor_owner_id |
| productId | productId | product_id |
| createdAt | createdAt | created_at |
| likeCount | likeCount | like_count |
| IsAvailable | IsAvailable | is_available |
| IsSaleable | IsSaleable | is_saleable |
| preparationDays | preparationDays | preparation_days |
| isFreeShipping | isFreeShipping | is_free_shipping |
| categoryTitle | categoryTitle | category_title |

### مرحله ۲: پیاده‌سازی CDC

```sql
-- جدول Audit
CREATE TABLE audit_log (
    audit_id, table_name, operation, record_id,
    old_data JSONB, new_data JSONB, changed_at, processed
);

-- Trigger روی vendors, products, reviews, users
CREATE TRIGGER trg_vendors_audit
    AFTER INSERT OR UPDATE ON vendors
    FOR EACH ROW EXECUTE FUNCTION vendors_audit_trigger_func();
```

**چرا Trigger-based CDC؟**
- سادگی پیاده‌سازی بدون نیاز به ابزار خارجی
- ثبت دقیق old_data و new_data برای Transform
- مناسب پروژه‌های آموزشی و سیستم‌های با حجم متوسط

### مرحله ۳: طراحی لایه تحلیلی ClickHouse

- استفاده از `ReplacingMergeTree` برای جداولی که UPDATE می‌شوند
- Denormalization: `category_title` و `vendor_status_title` در جداول dim ذخیره می‌شوند
- `fact_reviews` شامل `has_attachment`, `created_hour` به صورت Materialized Column

### مرحله ۴: بارگذاری افزایشی Python

اسکریپت `incremental_loader.py`:
1. هر ۶۰ ثانیه جدول `audit_log` را بررسی می‌کند
2. رکوردهای جدید (با `audit_id > last_audit_id`) را می‌خواند
3. **Transform:** تبدیل JSONB به ساختار ClickHouse، اعتبارسنجی کلیدها، نرمال‌سازی timestamp
4. **Load:** INSERT دسته‌ای (batch=500) به ClickHouse
5. رکوردها را `processed=TRUE` علامت‌گذاری می‌کند

### مرحله ۵: شبیه‌سازی تغییرات

اسکریپت `data_simulator.py` به مدت ۱۵ دقیقه:
- نظر جدید INSERT می‌کند
- like_count را UPDATE می‌کند
- stock محصول را تغییر می‌دهد
- امتیاز فروشنده را به‌روز می‌کند

### مرحله ۶: Data Marts

| Data Mart | هدف | کوئری مرتبط |
|-----------|------|-------------|
| `dm_top_vendors` | فروشندگان برتر هفتگی | Q6, DM1 |
| `dm_free_shipping_analysis` | بهینه‌سازی ارسال رایگان | DM2 |
| `dm_trending_categories` | دسته‌بندی‌های ترند | DM3 |
| `dm_review_engagement` | تأثیر عکس/ویدیو بر لایک | DM4 |

---

## ۴. نتیجه اجرای کوئری‌ها

### کوئری‌های تحلیلی (۱۰ کوئری)

| # | شرح | PostgreSQL | ClickHouse |
|---|------|------------|------------|
| 1 | اطلاعات فروشنده | JOIN vendors + vendor_statuses | SELECT از dim_vendors FINAL |
| 2 | میانگین امتیاز ساعتی | EXTRACT(HOUR) + GROUP BY | toHour() + GROUP BY |
| 3 | افزایش likeCount | UPDATE + CDC | ReplacingMergeTree |
| 4 | بررسی IsSaleable | CASE WHEN stock>0 | Materialized Column |
| 5 | نظرات ارسال/دیر | LIKE '%ارسال%' | LIKE با scan ستونی |
| 6 | استان‌های برتر | JOIN 3 جدول | JOIN + pre-aggregated |
| 7 | کلمات پرتکرار star=1 | CTE + unnest | arrayJoin + splitByChar |
| 8 | ۱۰ نظر آخر محصول | ORDER BY + LIMIT | ORDER BY + LIMIT |
| 9 | کاربران با نظر مثبت | LIKE + GROUP BY | LIKE + GROUP BY |
| 10 | INSERT نظر جدید | INSERT + Trigger | CDC → incremental load |

### نتایج بنچمارک (اجرای واقعی — داده‌های نمونه)

| کوئری | PostgreSQL (ms) | ClickHouse (ms) | توضیح |
|-------|-----------------|-----------------|-------|
| میانگین امتیاز ساعتی | 3.14 | 60.91 | داده کم — PG سریع‌تر |
| استان‌های برتر | 2.40 | 58.68 | JOIN سبک در PG |
| کلمات پرتکرار | 1.71 | 55.96 | حجم کم داده |
| کاربران نظر مثبت | 3.98 | 62.76 | overhead اتصال CH |

**Data Mart vs Raw Join (ClickHouse):**
| روش | زمان (ms) |
|-----|-----------|
| dm_top_vendors (پیش‌محاسبه) | 48.16 |
| JOIN خام dim_vendors + fact | 63.37 |

> **نکته مهم:** در حجم داده فعلی (~۵۰۰۰ نظر)، PostgreSQL سریع‌تر است چون ClickHouse برای مقیاس میلیون‌ها رکورد طراحی شده و overhead اتصال HTTP (~۵۰ms) در هر کوئری تأثیرگذار است. در مقیاس production با میلیون‌ها رکورد، ClickHouse ۱۰-۱۰۰ برابر سریع‌تر خواهد بود. Data Mart همچنان ~۲۵٪ سریع‌تر از JOIN خام است.

---

## ۵. پاسخ سؤالات تحلیلی

### سؤال ۱: مقایسه عملکرد کوئری‌ها در PostgreSQL و ClickHouse

**نتیجه:** در حجم داده پروژه (چند هزار رکورد)، PostgreSQL به دلیل داده در حافظه و عدم overhead اتصال، سریع‌تر است. اما در مقیاس production:

| ویژگی | PostgreSQL (Row-oriented) | ClickHouse (Column-oriented) |
|--------|--------------------------|------------------------------|
| ذخیره‌سازی | سطری (تمام فیلدها کنار هم) | ستونی (هر ستون جدا) |
| فشرده‌سازی | محدود | ۵-۲۰ برابر بهتر |
| Aggregation | Full row scan | فقط ستون‌های مورد نیاز |
| Index | B-Tree (مناسب point lookup) | Sparse Index (مناسب range scan) |
| JOIN | Hash/Nested Loop | Vectorized execution |
| نقطه عطف | تا ~۱M رکورد | از ~۱۰M رکورد به بالا |

PostgreSQL برای **تراکنش‌های تکی** (INSERT/UPDATE/SELECT by PK) بهینه است.  
ClickHouse برای **اسکن و تجمیع حجم بالا** (میلیون‌ها تا میلیاردها رکورد) طراحی شده است.

**تست CDC:** پس از شبیه‌سازی ۱ دقیقه‌ای، ۶ رکورد audit ثبت و با موفقیت به ClickHouse منتقل شدند.

---

### سؤال ۲: جایگاه مفاهیم ETL در خط لوله

| مفهوم | محل اجرا | توضیح |
|-------|----------|-------|
| **Extract** | PostgreSQL (audit_log) | Trigger تغییرات را ثبت می‌کند؛ Python رکوردهای جدید را می‌خواند |
| **Transform** | Python Script | تبدیل JSONB→ساختار ClickHouse، denormalization، اعتبارسنجی FK، نرمال‌سازی timestamp |
| **Load** | ClickHouse | INSERT دسته‌ای به جداول dim/fact |

**چرا Transform در Python و نه در دیتابیس؟**
1. **جداسازی مسئولیت‌ها (Separation of Concerns):** دیتابیس مبدأ فقط ثبت می‌کند، تبدیل در لایه میانی
2. **انعطاف‌پذیری:** تغییر قوانین Transform بدون تغییر Trigger/Schema
3. **قابلیت تست:** منطق Transform به صورت مستقل قابل تست است
4. **مقیاس‌پذیری:** در آینده می‌توان چند مقصد (ClickHouse, S3, Data Lake) داشت
5. **عدم بار اضافی روی OLTP:** تبدیل‌های سنگین روی سرور PostgreSQL اجرا نمی‌شوند

---

### سؤال ۳: مقایسه روش‌های Incremental Load

#### روش پیاده‌سازی شده: CDC مبتنی بر Audit Table (شبیه Timestamp-based)

```
SELECT * FROM audit_log WHERE audit_id > last_processed_id AND processed = FALSE
```

#### مقایسه با Timestamp-based

| معیار | Audit/CDC (پیاده‌سازی ما) | Timestamp-based |
|-------|--------------------------|-----------------|
| **دقت** | بالا — هر تغییر ثبت می‌شود | متوسط — اگر دو تغییر در یک timestamp باشد، ممکن است از دست برود |
| **اطلاعات تغییر** | old_data + new_data (نوع عملیات) | فقط رکورد جدید |
| **پیچیدگی** | بالاتر (نیاز به Trigger) | ساده‌تر (فقط WHERE updated_at > last_run) |
| **Overhead** | Trigger روی هر INSERT/UPDATE | بدون overhead در مبدأ |
| **حذف رکورد** | قابل شناسایی (operation='D') | غیرقابل شناسایی مگر soft delete |

**مزایای Audit-based:**
- ثبت دقیق نوع تغییر (Insert/Update/Delete)
- نگهداری old_data برای SCD Type 2
- عدم وابستگی به دقت ساعت سیستم

**معایب Audit-based:**
- افزایش حجم ذخیره‌سازی
- Overhead Trigger روی تراکنش‌ها

**سناریوی مناسب Timestamp-based:** سیستم‌هایی با حجم تغییرات کم و بدون نیاز به ردیابی دقیق تغییرات.

**سناریوی مناسب Audit/CDC:** سیستم‌هایی که نیاز به audit trail، ردیابی تغییرات و دقت بالا دارند (مثل پروژه ما).

---

### سؤال ۴: چالش‌های Trigger-based CDC

**دو عیب اصلی:**

1. **Overhead روی تراکنش‌های مبدأ:**
   - هر INSERT/UPDATE یک INSERT اضافی در audit_log انجام می‌دهد
   - در سیستم‌های با ۱۰,۰۰۰+ TPS، Trigger می‌تواند latency تراکنش‌ها را ۲-۵ برابر کند
   - قفل‌های اضافی (row-level lock) روی جدول audit_log

2. **وابستگی شدید به Schema:**
   - تغییر ساختار جدول (ALTER TABLE) نیاز به به‌روزرسانی Trigger دارد
   - افزودن جدول جدید نیاز به Trigger جدید دارد
   - در سیستم‌های بزرگ با صدها جدول، نگهداری Triggerها دشوار است

**راهکارهای جایگزین برای سیستم‌های بزرگ:**

| راهکار | توضیح |
|--------|-------|
| **Debezium + Kafka** | خواندن WAL (Write-Ahead Log) بدون تأثیر روی تراکنش |
| **PostgreSQL Logical Replication** | انتقال تغییرات در سطح WAL |
| **Maxwell's Daemon** | خواندن binlog/WAL و ارسال به صف پیام |
| **AWS DMS** | سرویس managed برای CDC |

این روش‌ها تغییرات را از **WAL** می‌خوانند و هیچ Trigger اضافی روی جداول نصب نمی‌کنند.

---

### سؤال ۵: Full Load vs بهینه‌سازی منابع و مشکل Small Files

#### مقایسه Batch Size

| حالت | Batch Size | تأثیر |
|------|-----------|-------|
| بدترین | 1 (تک‌رکوردی) | هر رکورد یک فایل part جدید → هزاران فایل کوچک |
| بهینه | 500 (پیش‌فرض ما) | تعادل بین latency و تعداد فایل |
| Full Load | تمام داده | یکباره بارگذاری — مناسب بارگذاری اولیه |

**مشکل Small Files در ClickHouse:**
- هر INSERT یک **part** جدید در دیسک ایجاد می‌کند
- partهای زیاد → merge‌های مکرر → مصرف CPU/RAM/I/O بالا
- کوئری‌ها باید partهای بیشتری را اسکن کنند → کندی

**تأثیر Batch Size = 1:**
- ۵۰۰۰ رکورد = ۵۰۰۰ part → انفجار metadata
- RAM برای نگه‌داری metadata partها
- I/O bandwidth هدر می‌رود در merge

**نقش فرکانس اجرا:**
- اجرای هر ۱ ثانیه با batch کوچک → partهای زیاد
- اجرای هر ۶۰ ثانیه با batch ۵۰۰ → partهای کمتر و بزرگ‌تر
- فرکانس پایین‌تر = partهای بزرگ‌تر = merge کمتر = عملکرد بهتر

در پروژه ما: `POLL_INTERVAL_SECONDS=60` و `BATCH_SIZE=500` برای تعادل بهینه انتخاب شده.

---

### سؤال ۶: مفهوم Non-Volatile و UPDATE در ClickHouse

**Non-Volatile:** داده‌های بارگذاری‌شده در انبار داده **حذف یا بازنویسی نمی‌شوند** — فقط افزوده می‌شوند.

**در معماری ما:**
- PostgreSQL: `UPDATE products SET stock = 50` → رکورد بازنویسی می‌شود
- CDC: old_data + new_data در audit_log ثبت می‌شود
- ClickHouse: یک رکورد **جدید** با `_version` بالاتر INSERT می‌شود
- `ReplacingMergeTree`: در زمان merge، فقط آخرین version نگه داشته می‌شود

**وقتی رکورد در PostgreSQL UPDATE می‌شود:**
1. Trigger رویداد UPDATE را در audit_log ثبت می‌کند
2. Python loader رکورد جدید را با `_version` جدید به ClickHouse می‌فرستد
3. هر دو نسخه (قدیم و جدید) موقتاً وجود دارند
4. پس از merge، فقط نسخه جدید باقی می‌ماند (SCD Type 1)

**ارتباط با SCD Type 2:**
- SCD Type 1 (پیاده‌سازی ما): نسخه قدیمی **بازنویسی** می‌شود
- SCD Type 2: نسخه قدیمی **حفظ** می‌شود با `valid_from`/`valid_to`
- برای SCD Type 2 باید از `old_data` در audit_log استفاده و رکورد جدید با timestamp جدید INSERT شود

---

### سؤال ۷: Batch Processing vs Real-time Processing

**معماری فعلی ما: Batch Processing (Micro-batch)**
- Python loader هر ۶۰ ثانیه audit_log را بررسی می‌کند
- Latency: حداکثر ۶۰ ثانیه
- پیچیدگی: پایین
- مناسب: داشبوردهای مدیریتی، گزارش‌های روزانه

| معیار | Batch (فعلی) | Real-time |
|-------|-------------|-----------|
| Latency | ۳۰-۶۰ ثانیه | زیر ۱ ثانیه |
| پیچیدگی | پایین | بالا (Kafka, Flink) |
| هزینه زیرساخت | پایین | بالا |
| مصرف منابع | متناوب | مداوم |

**سناریو: فروشگاه آنلاین با ۱۰,۰۰۰ تراکنش/روز**

با ۱۰,۰۰۰ تراکنش در روز (~۷ تراکنش/دقیقه):
- **Batch (هر ۱ دقیقه):** کاملاً مناسب — داده با تأخیر حداکثر ۱ دقیقه در انبار تحلیلی خواهد بود
- **Real-time:** over-engineering — هزینه بالا بدون نیاز واقعی

**اگر حجم به ۱۰,۰۰۰ تراکنش/دقیقه برسد:**
- Batch با polling دیگر مناسب نیست
- **Kafka + Flink/Spark Streaming** توصیه می‌شود
- Debezium برای CDC از WAL به جای Trigger

---

### سؤال ۸: فناوری‌های جایگزین برای Real-time Analysis

| فناوری | Latency | مقایسه با معماری فعلی |
|---------|---------|----------------------|
| **Apache Kafka + ClickHouse (Kafka Engine)** | ۱-۵ ثانیه | جایگزین polling؛ داده از WAL به Kafka و مستقیم به ClickHouse |
| **Apache Flink** | زیر ۱ ثانیه | پردازش stream با state management؛ پیچیدگی بالا |
| **Apache Spark Structured Streaming** | ۲-۱۰ ثانیه | micro-batch روی Spark؛ مناسب ETL سنگین |
| **Debezium + Kafka Connect** | ۱-۳ ثانیه | CDC بدون Trigger؛ استاندارد صنعتی |
| **Materialize** | زیر ۱ ثانیه | پایگاه داده streaming SQL؛ مناسب view‌های real-time |

**مقایسه تفصیلی:**

```
معماری فعلی:     PG → Trigger → Audit → Python(poll) → ClickHouse
                 Latency: ~60s | Cost: Low | Complexity: Low

Kafka-based:     PG → Debezium → Kafka → ClickHouse Engine
                 Latency: ~3s | Cost: Medium | Complexity: Medium

Flink-based:     PG → Debezium → Kafka → Flink → ClickHouse
                 Latency: <1s | Cost: High | Complexity: High
```

**توصیه برای فروشگاه ۱۰K تراکنش/روز:** معماری Batch فعلی کافی است.  
**توصیه برای ۱۰K تراکنش/دقیقه:** Kafka + ClickHouse Kafka Engine.

---

## ۶. جمع‌بندی

در این پروژه یک خط لوله داده کامل از OLTP به OLAP پیاده‌سازی شد:

✅ محیط Docker با PostgreSQL، ClickHouse و Python  
✅ Schema نرمال‌شده OLTP با ۸ جدول اصلی  
✅ لایه CDC با Audit Table و Trigger  
✅ بارگذاری اولیه صرفاً با Python  
✅ شبیه‌سازی تغییرات دوره‌ای  
✅ Schema بهینه ClickHouse با Star Schema  
✅ بارگذار افزایشی با polling دوره‌ای  
✅ ۱۰ کوئری تحلیلی در هر دو پایگاه داده  
✅ ۴ Data Mart برای بهینه‌سازی کوئری  
✅ بنچمارک مقایسه‌ای عملکرد  

**درس آموخته‌شده:** انتخاب معماری مناسب (Batch vs Real-time) باید بر اساس نیاز واقعی به latency و حجم داده باشد، نه صرفاً استفاده از فناوری‌های پیچیده‌تر.

---

*پایان گزارش*
