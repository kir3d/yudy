PRAGMA foreign_keys = ON;

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE legal_documents (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('TERMS_OF_USE', 'PRIVACY_POLICY', 'PERSONAL_DATA_CONSENT')),
    version TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_mandatory INTEGER NOT NULL DEFAULT 1 CHECK (is_mandatory IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    UNIQUE (type, version)
);
CREATE UNIQUE INDEX uq_legal_active_type ON legal_documents(type) WHERE active = 1;

CREATE TABLE user_consents (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    legal_document_id TEXT NOT NULL REFERENCES legal_documents(id),
    accepted_at TEXT NOT NULL,
    UNIQUE (user_id, legal_document_id)
);

CREATE TABLE goals (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE interests (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('SECTOR', 'THEME')),
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE regions (
    id TEXT PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE user_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    experience TEXT NOT NULL CHECK (experience IN ('NEW', 'SOME', 'REGULAR', 'EXPERIENCED')),
    investment_horizon TEXT NOT NULL CHECK (investment_horizon IN ('UNDER_ONE', 'ONE_THREE', 'THREE_FIVE', 'FIVE_PLUS')),
    onboarding_completed INTEGER NOT NULL DEFAULT 1 CHECK (onboarding_completed IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE user_goals (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    goal_id TEXT NOT NULL REFERENCES goals(id),
    PRIMARY KEY (user_id, goal_id)
);

CREATE TABLE user_interests (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interest_id TEXT NOT NULL REFERENCES interests(id),
    PRIMARY KEY (user_id, interest_id)
);

CREATE TABLE user_excluded_interests (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interest_id TEXT NOT NULL REFERENCES interests(id),
    PRIMARY KEY (user_id, interest_id)
);

CREATE TABLE user_regions (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    region_id TEXT NOT NULL REFERENCES regions(id),
    PRIMARY KEY (user_id, region_id)
);

CREATE TABLE risk_questionnaires (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL,
    conservative_max INTEGER NOT NULL,
    balanced_max INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    CHECK (conservative_max >= 0 AND conservative_max < balanced_max AND balanced_max < 100)
);
CREATE UNIQUE INDEX uq_risk_active ON risk_questionnaires(active) WHERE active = 1;

CREATE TABLE risk_questions (
    id TEXT PRIMARY KEY,
    questionnaire_id TEXT NOT NULL REFERENCES risk_questionnaires(id),
    code TEXT NOT NULL,
    text TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    UNIQUE (questionnaire_id, code)
);
CREATE INDEX ix_risk_questions_questionnaire ON risk_questions(questionnaire_id);

CREATE TABLE risk_answer_options (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL REFERENCES risk_questions(id),
    code TEXT NOT NULL,
    text TEXT NOT NULL,
    score INTEGER NOT NULL CHECK (score >= 0),
    sort_order INTEGER NOT NULL,
    UNIQUE (question_id, code)
);
CREATE INDEX ix_risk_options_question ON risk_answer_options(question_id);

CREATE TABLE risk_profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    risk_score INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
    risk_category TEXT NOT NULL CHECK (risk_category IN ('Conservative', 'Balanced', 'Growth')),
    questionnaire_version TEXT NOT NULL REFERENCES risk_questionnaires(version),
    answers TEXT NOT NULL CHECK (json_valid(answers)),
    calculated_at TEXT NOT NULL
);

CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('STOCK', 'ETF')),
    description TEXT NOT NULL,
    sector TEXT,
    industry TEXT,
    country TEXT,
    region TEXT,
    market TEXT,
    logo_url TEXT,
    currency TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX ix_assets_symbol ON assets(symbol);
CREATE INDEX ix_assets_type ON assets(asset_type);
CREATE INDEX ix_assets_region ON assets(region);
CREATE INDEX ix_assets_sector ON assets(sector);

CREATE TABLE asset_themes (
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    interest_id TEXT NOT NULL REFERENCES interests(id),
    PRIMARY KEY (asset_id, interest_id)
);

CREATE TABLE asset_fundamentals (
    asset_id TEXT PRIMARY KEY REFERENCES assets(id) ON DELETE CASCADE,
    price REAL,
    market_cap REAL,
    pe REAL,
    eps REAL,
    revenue REAL,
    revenue_growth REAL,
    net_income REAL,
    debt REAL,
    cash_flow REAL,
    dividend REAL,
    dividend_yield REAL,
    updated_at TEXT NOT NULL
);

CREATE TABLE asset_prices (
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL,
    PRIMARY KEY (asset_id, timestamp)
);
CREATE INDEX ix_asset_prices_asset_timestamp ON asset_prices(asset_id, timestamp);

CREATE TABLE tokenized_assets (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    token_name TEXT NOT NULL,
    issuer TEXT,
    tokenization_provider TEXT,
    backing TEXT,
    proof_of_reserves_url TEXT,
    oracle_provider TEXT,
    oracle_reference TEXT,
    corporate_actions_info TEXT,
    availability TEXT,
    external_provider_id TEXT,
    external_buy_url TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (asset_id, symbol)
);
CREATE INDEX ix_tokenized_assets_asset ON tokenized_assets(asset_id);

CREATE TABLE asset_risks (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);
CREATE INDEX ix_asset_risks_asset ON asset_risks(asset_id);

CREATE TABLE asset_interaction_states (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    liked INTEGER NOT NULL DEFAULT 0 CHECK (liked IN (0, 1)),
    disliked INTEGER NOT NULL DEFAULT 0 CHECK (disliked IN (0, 1)),
    saved INTEGER NOT NULL DEFAULT 0 CHECK (saved IN (0, 1)),
    PRIMARY KEY (user_id, asset_id),
    CHECK (NOT (liked AND disliked))
);

CREATE TABLE asset_interactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('LIKE', 'UNLIKE', 'DISLIKE', 'REMOVE_DISLIKE', 'SAVE', 'UNSAVE', 'VIEW', 'BUY_CLICK')),
    metadata TEXT CHECK (metadata IS NULL OR json_valid(metadata)),
    created_at TEXT NOT NULL
);
CREATE INDEX ix_interactions_user_asset ON asset_interactions(user_id, asset_id);
CREATE INDEX ix_interactions_user_type ON asset_interactions(user_id, type);
CREATE INDEX ix_interactions_asset_type ON asset_interactions(asset_id, type);
CREATE INDEX ix_interactions_created ON asset_interactions(created_at);

CREATE TABLE learn_articles (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    content TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE analytics_events (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    event_name TEXT NOT NULL,
    properties TEXT NOT NULL CHECK (json_valid(properties)),
    created_at TEXT NOT NULL
);
CREATE INDEX ix_analytics_event_created ON analytics_events(event_name, created_at);
CREATE INDEX ix_analytics_user_created ON analytics_events(user_id, created_at);
