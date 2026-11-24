CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,
    record_id VARCHAR(100) NOT NULL,
    operation VARCHAR(8) NOT NULL,
    old_values JSON NOT NULL,
    new_values JSON,
    action_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mysql_user VARCHAR(288) NOT NULL,
    INDEX idx_audit_record (table_name, record_id, action_at)
);
