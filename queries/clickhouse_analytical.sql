-- ============================================================
-- Analytical Queries - ClickHouse (OLAP) - BaSalam Data
-- ============================================================

-- Q1: اطلاعات غرفه
SELECT DISTINCT
    vendor_name, vendor_score, vendor_status_title, vendor_owner_id
FROM dim_products FINAL
WHERE vendor_id = 783928;

-- Q2: میانگین امتیاز ساعتی
SELECT
    toHour(created_at) AS review_hour,
    avg(star) AS avg_rating,
    count() AS review_count
FROM fact_reviews FINAL
GROUP BY review_hour
ORDER BY review_hour;

-- Q3: بیشترین likeCount
SELECT review_id, product_id, like_count, created_at
FROM fact_reviews FINAL
WHERE like_count > 0
ORDER BY like_count DESC
LIMIT 20;

-- Q4: IsAvailable و IsSaleable
SELECT product_id, stock, is_available, is_saleable
FROM dim_products FINAL
WHERE product_id = 9873883;

-- Q5: نظرات ارسال/دیر با امتیاز پایین
SELECT review_id, product_id, star, description
FROM fact_reviews FINAL
WHERE (description LIKE '%ارسال%' OR description LIKE '%دیر%')
  AND star < 4
LIMIT 50;

-- Q6: استان‌ها/شهرهای برتر
SELECT
    vendor_province_id,
    vendor_owner_city,
    avg(vendor_score) AS avg_vendor_score,
    sum(sales_count_week) AS total_weekly_sales,
    avg(rating_average) AS avg_rating
FROM dim_products FINAL
WHERE vendor_province_id > 0
GROUP BY vendor_province_id, vendor_owner_city
ORDER BY avg_vendor_score DESC, total_weekly_sales DESC
LIMIT 10;

-- Q7: ۱۰ کلمه پرتکرار در star=1
SELECT
    arrayJoin(splitByChar(' ', description)) AS word,
    count() AS frequency
FROM fact_reviews FINAL
WHERE star = 1 AND length(word) > 2
GROUP BY word
ORDER BY frequency DESC
LIMIT 10;

-- Q8: ۱۰ نظر آخر عمومی
SELECT review_id, product_id, user_id, star, description, created_at
FROM fact_reviews FINAL
WHERE product_id = 824662 AND is_public = 1
ORDER BY created_at DESC
LIMIT 10;

-- Q9: کاربران با نظرات مثبت
SELECT user_id, count() AS positive_review_count
FROM fact_reviews FINAL
WHERE description LIKE '%عالی%' OR description LIKE '%خوشمزه%' OR description LIKE '%خوب%'
GROUP BY user_id
ORDER BY positive_review_count DESC
LIMIT 10;

-- ============================================================
-- Data Mart Queries (Stage 6)
-- ============================================================

-- DM1: Top Vendors
SELECT vendor_id, vendor_name, weekly_sales, rating_average
FROM dm_top_vendors
ORDER BY weekly_sales DESC
LIMIT 10;

-- DM2: Free Shipping Campaign
SELECT preparation_days, is_free_shipping, avg(rating_average), sum(sales_count_week)
FROM dm_free_shipping_analysis
GROUP BY preparation_days, is_free_shipping
ORDER BY preparation_days;

-- DM3: Trending Categories
SELECT category_title, monthly_reviews, weekly_sales
FROM dm_trending_categories
ORDER BY monthly_reviews DESC
LIMIT 10;

-- DM4: Review Engagement (تأثیر attachment بر likeCount)
SELECT
    has_attachment,
    avg(like_count) AS avg_likes,
    count() AS review_count
FROM dm_review_engagement
GROUP BY has_attachment;
