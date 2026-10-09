PRAGMA foreign_keys = ON;

-- Schema changes intentionally reset all application user data. Supabase Auth
-- identities remain external and recreate their D1 row on the next sign-in.
DELETE FROM analytics_events;
DELETE FROM users;

ALTER TABLE users ADD COLUMN agreements_accepted_at TEXT;
