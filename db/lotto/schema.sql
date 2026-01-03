-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 로또 6/45 당첨 번호 테이블
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS lotto_draws (
    draw_no INTEGER PRIMARY KEY,
    draw_date DATE NOT NULL,
    n1 SMALLINT NOT NULL CHECK (n1 BETWEEN 1 AND 45),
    n2 SMALLINT NOT NULL CHECK (n2 BETWEEN 1 AND 45),
    n3 SMALLINT NOT NULL CHECK (n3 BETWEEN 1 AND 45),
    n4 SMALLINT NOT NULL CHECK (n4 BETWEEN 1 AND 45),
    n5 SMALLINT NOT NULL CHECK (n5 BETWEEN 1 AND 45),
    n6 SMALLINT NOT NULL CHECK (n6 BETWEEN 1 AND 45),
    bonus SMALLINT NOT NULL CHECK (bonus BETWEEN 1 AND 45),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lotto_draws_date ON lotto_draws(draw_date);
CREATE INDEX IF NOT EXISTS idx_lotto_draws_created ON lotto_draws(created_at);

COMMENT ON TABLE lotto_draws IS '로또 6/45 당첨 번호 (2002년~현재)';
COMMENT ON COLUMN lotto_draws.draw_no IS '회차 번호';
COMMENT ON COLUMN lotto_draws.draw_date IS '추첨일';
COMMENT ON COLUMN lotto_draws.bonus IS '보너스 번호';

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 통계 캐시 테이블 (주 1회 갱신)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS lotto_stats_cache (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    updated_at TIMESTAMP NOT NULL,
    total_draws INTEGER NOT NULL,
    most_common JSONB NOT NULL,
    least_common JSONB NOT NULL,
    ai_scores JSONB NOT NULL
);

COMMENT ON TABLE lotto_stats_cache IS '로또 통계 캐시 (단일 레코드, 매주 갱신)';
COMMENT ON COLUMN lotto_stats_cache.most_common IS '최다 출현 번호 15개 (JSON 배열)';
COMMENT ON COLUMN lotto_stats_cache.least_common IS '최소 출현 번호 15개 (JSON 배열)';
COMMENT ON COLUMN lotto_stats_cache.ai_scores IS 'AI 점수 (JSON 객체: {번호: 점수})';

-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
-- 추천 로그 테이블 (나중에 패턴 분석용)
-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CREATE TABLE IF NOT EXISTS lotto_recommend_logs (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    target_draw_no INTEGER NOT NULL,
    lines JSONB NOT NULL,
    recommend_time TIMESTAMP DEFAULT NOW(),
    match_results JSONB DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_lotto_logs_user ON lotto_recommend_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_lotto_logs_draw ON lotto_recommend_logs(target_draw_no);
CREATE INDEX IF NOT EXISTS idx_lotto_logs_time ON lotto_recommend_logs(recommend_time);

COMMENT ON TABLE lotto_recommend_logs IS '유저별 로또 추천 이력 및 당첨 결과';
COMMENT ON COLUMN lotto_recommend_logs.target_draw_no IS '추천 대상 회차';
COMMENT ON COLUMN lotto_recommend_logs.lines IS '6줄 추천 번호 (JSON 배열)';
COMMENT ON COLUMN lotto_recommend_logs.match_results IS '당첨 후 일치 개수 (JSON 객체)';
