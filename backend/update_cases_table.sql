-- 更新cases表，添加photo_path字段
-- 如果字段已存在，会报错，可以忽略

-- 添加photo_path字段
ALTER TABLE cases ADD COLUMN photo_path VARCHAR(500);

-- 如果需要添加其他缺失的字段，可以在这里添加
-- ALTER TABLE cases ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;
-- ALTER TABLE cases ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
