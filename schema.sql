CREATE TABLE IF NOT EXISTS embeds (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE, 
    embed JSON,
    creator_id BIGINT
);

CREATE TABLE IF NOT EXISTS layouts (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE, 
    content TEXT,
    embeds TEXT,
    creator_id BIGINT
);

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

CREATE TABLE IF NOT EXISTS code_responders (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    trigger TEXT,
    detection TEXT,
    code TEXT,
    cooldown TEXT,
    author_id BIGINT
);

CREATE TABLE IF NOT EXISTS auto_messages (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE,
    channel_id BIGINT,
    layout JSON,
    interval INTEGER,
    lastsent INTEGER
);

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

CREATE TABLE IF NOT EXISTS active_tickets (
  ticket_id SERIAL PRIMARY KEY,
  channel_id BIGINT,
  opener_id BIGINT,
  timestamp INTEGER,
  archive_id BIGINT,
  remind_after TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
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
  item_name_id TEXT,
  state TEXT,
  item_count INTEGER,
  time_acquired TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  time_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, item_name_id)
);

CREATE TABLE IF NOT EXISTS shop_items (
  name_id TEXT PRIMARY KEY,
  number_id INTEGER UNIQUE,
  display_name TEXT,
  price INTEGER,
  sell_price INTEGER DEFAULT NULL,
  stock INTEGER DEFAULT -1,
  usable BOOLEAN,
  activatable BOOLEAN,
  category TEXT,
  description TEXT
);

CREATE TABLE IF NOT EXISTS item_categories (
  name TEXT PRIMARY KEY,
  display_name TEXT,
  description TEXT
);

CREATE TABLE IF NOT EXISTS item_reqs( 
  item_name_id TEXT,
  type TEXT,  
  description TEXT,
  name TEXT,
  UNIQUE(item_name_id, type, name)
);

CREATE TABLE IF NOT EXISTS joins (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  guild_id BIGINT,
  member_count INTEGER,
  time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);  

CREATE TABLE IF NOT EXISTS leaves (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  guild_id BIGINT,
  member_count INTEGER,
  time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_data (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  channel_id BIGINT,
  time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS afk (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  message TEXT,
  start_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS timezones (
  user_id BIGINT PRIMARY KEY,
  timezone TEXT
);

CREATE TABLE IF NOT EXISTS event_dailies (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  date_str TEXT,
  task TEXT,
  num INTEGER DEFAULT 1,
  claimed BOOLEAN DEFAULT FALSE,
  UNIQUE(user_id, date_str, task)
);

CREATE TABLE IF NOT EXISTS event_dailies_bonuses (
  id SERIAL PRIMARY KEY,
  user_id BIGINT,
  date_str TEXT 
);

CREATE TABLE IF NOT EXISTS welc_messages (
  user_id BIGINT PRIMARY KEY,
  channel_id BIGINT,
  message_id BIGINT,
  time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_welc_messages (
  message_id BIGINT PRIMARY KEY,
  bot_message_id BIGINT,
  channel_id BIGINT
);

CREATE TABLE IF NOT EXISTS welc_messages (
  user_id BIGINT PRIMARY KEY,
  channel_id BIGINT,
  message_id BIGINT,
  time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS intro_messages (
  id SERIAL PRIMARY KEY,
  message_id BIGINT,
  channel_id BIGINT,
  associated_user_id BIGINT,
  bot BOOLEAN
);

CREATE TABLE IF NOT EXISTS guild_server_joins(
  id SERIAL PRIMARY KEY,
  guild_id BIGINT, 
  user_id BIGINT,
  joined_at TIMESTAMP WITH TIME ZONE,
  UNIQUE(guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS exclusive_roles (
  id SERIAL PRIMARY KEY,
  guild_id BIGINT,
  group_name TEXT,
  role_id BIGINT
);
