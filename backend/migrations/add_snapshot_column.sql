-- 为 operation_logs 表添加 snapshot_data 列，用于存储变更前完整快照
ALTER TABLE operation_logs
  ADD COLUMN snapshot_data TEXT COMMENT '变更前快照JSON';
