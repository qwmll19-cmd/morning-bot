-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 로또 6/45 당첨 번호 테이블 (SQLite)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS lotto_draws (
    draw_no INTEGER PRIMARY KEY,
    draw_date TEXT NOT NULL,
    n1 INTEGER NOT NULL CHECK (n1 BETWEEN 1 AND 45),
    n2 INTEGER NOT NULL CHECK (n2 BETWEEN 1 AND 45),
    n3 INTEGER NOT NULL CHECK (n3 BETWEEN 1 AND 45),
    n4 INTEGER NOT NULL CHECK (n4 BETWEEN 1 AND 45),
    n5 INTEGER NOT NULL CHECK (n5 BETWEEN 1 AND 45),
    n6 INTEGER NOT NULL CHECK (n6 BETWEEN 1 AND 45),
    bonus INTEGER NOT NULL CHECK (bonus BETWEEN 1 AND 45),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lotto_draws_date ON lotto_draws(draw_date);

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 통계 캐시 테이블 (SQLite)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS lotto_stats_cache (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    updated_at DATETIME NOT NULL,
    total_draws INTEGER NOT NULL,
    most_common TEXT NOT NULL,
    least_common TEXT NOT NULL,
    ai_scores TEXT NOT NULL
);

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 추천 로그 테이블 (SQLite)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS lotto_recommend_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    target_draw_no INTEGER NOT NULL,
    lines TEXT NOT NULL,
    recommend_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    match_results TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_lotto_logs_user ON lotto_recommend_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_lotto_logs_draw ON lotto_recommend_logs(target_draw_no);
