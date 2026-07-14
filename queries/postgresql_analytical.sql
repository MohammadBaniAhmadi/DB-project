-- ============================================================
-- Analytical Queries - PostgreSQL (OLTP) - BaSalam Data
-- ============================================================

-- Q1: اطلاعات غرفه بر اساس vendor_id
SELECT DISTINCT
    vendor_name,
    vendor_score,
    vendor_status_title,
    vendor_owner_id
FROM products
WHERE vendor_id = 783928;

-- Q2: استخراج ساعت از created_at و میانگین امتیاز ساعتی
SELECT
    EXTRACT(HOUR FROM created_at) AS review_hour,
    AVG(star) AS avg_rating,
    COUNT(*) AS review_count
FROM reviews
GROUP BY EXTRACT(HOUR FROM created_at)
ORDER BY review_hour;

-- Q3: افزایش likeCount (نمایش نظرات با بیشترین لایک)
SELECT review_id, product_id, like_count, updated_at
FROM reviews
WHERE like_count > 0
ORDER BY like_count DESC
LIMIT 20;

-- Q4: بررسی IsAvailable و IsSaleable
SELECT
    product_id,
    stock,
    is_available AS "IsAvailable",
    is_saleable AS "IsSaleable",
    CASE WHEN stock > 0 AND is_available THEN TRUE ELSE FALSE END AS computed_saleable
FROM products
WHERE product_id = 9873883;

-- Q5: نظرات با «ارسال» یا «دیر» در description و star < 4
SELECT review_id, product_id, star, description
FROM reviews
WHERE (description LIKE '%ارسال%' OR description LIKE '%دیر%')
  AND star < 4
LIMIT 50;

-- Q6: استان‌ها/شهرها با بیشترین vendor_score یا sales_count_week
SELECT
    vendor_province_id,
    vendor_owner_city,
    AVG(vendor_score) AS avg_vendor_score,
    SUM(sales_count_week) AS total_weekly_sales,
    AVG(rating_average) AS avg_rating
FROM products
WHERE vendor_province_id IS NOT NULL
GROUP BY vendor_province_id, vendor_owner_city
ORDER BY avg_vendor_score DESC, total_weekly_sales DESC
LIMIT 10;

-- Q7: کلمات پرتکرار در نظرات star=1
WITH words AS (
    SELECT unnest(string_to_array(description, ' ')) AS word
    FROM reviews
    WHERE star = 1 AND description IS NOT NULL
)
SELECT word, COUNT(*) AS frequency
FROM words
WHERE length(word) > 2
GROUP BY word
ORDER BY frequency DESC
LIMIT 10;

-- Q8: ۱۰ نظر آخر عمومی برای یک محصول
SELECT review_id, product_id, user_id, star, description, created_at
FROM reviews
WHERE product_id = 824662 AND is_public = TRUE
ORDER BY created_at DESC
LIMIT 10;

-- Q9: کاربران با بیشترین نظر حاوی «عالی»، «خوشمزه»، «خوب»
SELECT
    user_id,
    COUNT(*) AS positive_review_count
FROM reviews
WHERE description LIKE '%عالی%'
   OR description LIKE '%خوشمزه%'
   OR description LIKE '%خوب%'
GROUP BY user_id
ORDER BY positive_review_count DESC
LIMIT 10;

-- Q10: INSERT نظر جدید (نمونه)
-- INSERT INTO reviews (review_id, product_id, user_id, star, description, is_public, created_at, updated_at)
-- VALUES ('new_review_001', 824662, 15127771, 5, 'محصول عالی و باکیفیت', TRUE, NOW(), NOW());
