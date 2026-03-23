-- 创建 business_cases 表
-- 用于存储合并的案件数据

SET NAMES utf8mb4;

DROP TABLE IF EXISTS business_cases;

CREATE TABLE business_cases (
    `序号` BIGINT,
    `月份` TEXT,
    `任务号` TEXT,
    `问题来源` TEXT,
    `监督员` TEXT,
    `上报时间` TEXT,
    `问题类型` TEXT,
    `大类名称` TEXT,
    `小类名称` TEXT,
    `所属片区` TEXT,
    `问题描述` TEXT,
    `地址描述` TEXT,
    `所属街道` TEXT,
    `所属社区` TEXT,
    `处置部门` TEXT,
    `捆绑处置截止时间` TEXT,
    `结案时间` TEXT,
    `当前阶段名称` TEXT,
    `是否超时` TEXT,
    `延期次数` BIGINT,
    `返工次数` TEXT,
    data_month VARCHAR(20)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 验证表结构
DESCRIBE business_cases;