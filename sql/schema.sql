CREATE TABLE IF NOT EXISTS djinni_market_data (
    id SERIAL PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    category VARCHAR(255) NOT NULL,
    experience_years VARCHAR(50) NOT NULL,
    work_format VARCHAR(50) NOT NULL,
    candidates_count INTEGER,
    jobs_count INTEGER,
    average_salary INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_market_snapshot UNIQUE (snapshot_date, category, experience_years, work_format)
);