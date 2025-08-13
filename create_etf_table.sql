CREATE TABLE IF NOT EXISTS etf_data (
    code VARCHAR(20) PRIMARY KEY,
    name VARCHAR(255),
    market VARCHAR(10),
    price DECIMAL(10, 4),
    change_percent DECIMAL(10, 4),
    volume BIGINT,
    amount DECIMAL(20, 4),
    update_time DATETIME
);