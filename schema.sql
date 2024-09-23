-- temporary deletion 
-- rename arthof to art_hof if exists 
ALTER TABLE IF EXISTS arthof RENAME TO art_hof;

CREATE TABLE IF NOT EXISTS embeds (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE, 
    embed JSON,
    creator_id BIGINT
);
--DROP TABLE IF EXISTS layouts; 
CREATE TABLE IF NOT EXISTS layouts (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE, 
    content TEXT,
    embeds TEXT,
    creator_id BIGINT
);
--DROP TABLE IF EXISTS auto_responders;
CREATE TABLE IF NOT EXISTS auto_responders (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    trigger TEXT,
    detection TEXT,
    actions TEXT,
    restrictions TEXT,
    cooldown TEXT,
    author_id BIGINT
);
--DROP TABLE IF EXISTS code_responders;
CREATE TABLE IF NOT EXISTS code_responders (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    trigger TEXT,
    detection TEXT,
    code TEXT,
    cooldown TEXT,
    author_id BIGINT
);

--DROP TABLE IF EXISTS auto_messages;
CREATE TABLE IF NOT EXISTS auto_messages (
    name TEXT UNIQUE,
    channel_id BIGINT,
    layout JSON,
    interval INTEGER,
    lastsent INTEGER
);

--DROP TABLE IF EXISTS sticky_messages;
CREATE TABLE IF NOT EXISTS sticky_messages (
    id SERIAL PRIMARY KEY,
    channel_id BIGINT UNIQUE,
    layout JSON,
    last_message_id BIGINT DEFAULT NULL
);
CREATE TABLE IF NOT EXISTS future_tasks (
  id SERIAL PRIMARY KEY,
  action TEXT,
  data JSONB,
  time TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS todos (
  id SERIAL PRIMARY KEY,
  name TEXT,
  priority INTEGER,
  completed BOOLEAN,
  creator_id BIGINT,
  time_created TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  time_completed TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS sticky_roles (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  role_id BIGINT,
  until TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS bump_remind (
  user_id BIGINT,
  next_bump TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS cooldowns (
  id SERIAL PRIMARY KEY,
  action TEXT,
  user_id BIGINT,
  end_time TIMESTAMP WITH TIME ZONE,
  UNIQUE(action, user_id)
);

CREATE TABLE IF NOT EXISTS ticket_transcripts (
  id SERIAL PRIMARY KEY,
  ticket_id BIGINT,
  opener_id BIGINT,
  messages JSONB
);

CREATE TABLE IF NOT EXISTS confessions (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  confession TEXT
);

CREATE TABLE IF NOT EXISTS counters (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE,
  count INTEGER
);

CREATE TABLE IF NOT EXISTS queues (
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE,
  items JSONB
);

CREATE TABLE IF NOT EXISTS balances (
  id SERIAL PRIMARY KEY,
  user_id BIGINT UNIQUE,
  balance INTEGER
);

CREATE TABLE IF NOT EXISTS user_items (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  item_id BIGINT,
  amount INTEGER
);


CREATE TABLE IF NOT EXISTS shop_items (
  id INTEGER PRIMARY KEY,
  name_id TEXT UNIQUE,
  display_name TEXT,
  price INTEGER,
  properties JSONB
);