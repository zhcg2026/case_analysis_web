SET NAMES utf8mb4;
UPDATE business_cases SET data_month = `月份` WHERE data_month IS NULL AND `月份` IS NOT NULL;
SELECT DISTINCT data_month FROM business_cases WHERE data_month IS NOT NULL;