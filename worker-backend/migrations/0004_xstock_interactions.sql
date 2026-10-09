CREATE TABLE xstock_interaction_states (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    xstock_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    liked INTEGER NOT NULL DEFAULT 0 CHECK (liked IN (0, 1)),
    disliked INTEGER NOT NULL DEFAULT 0 CHECK (disliked IN (0, 1)),
    saved INTEGER NOT NULL DEFAULT 0 CHECK (saved IN (0, 1)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, xstock_id),
    CHECK (NOT (liked AND disliked))
);

CREATE TABLE xstock_interactions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    xstock_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN (
        'LIKE', 'UNLIKE', 'DISLIKE', 'REMOVE_DISLIKE', 'SAVE', 'UNSAVE', 'BUY_CLICK'
    )),
    metadata TEXT CHECK (metadata IS NULL OR json_valid(metadata)),
    created_at TEXT NOT NULL
);

CREATE INDEX ix_xstock_states_user_saved
    ON xstock_interaction_states(user_id, saved);
CREATE INDEX ix_xstock_interactions_user_asset
    ON xstock_interactions(user_id, xstock_id);
CREATE INDEX ix_xstock_interactions_user_type
    ON xstock_interactions(user_id, type);
CREATE INDEX ix_xstock_interactions_created
    ON xstock_interactions(created_at);
