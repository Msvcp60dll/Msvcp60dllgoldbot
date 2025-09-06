-- Quick Whitelist Import Template
-- Use this if you already have a list of user IDs to whitelist
-- Replace the user IDs below with your actual member IDs

-- Ensure whitelist table exists
CREATE TABLE IF NOT EXISTS whitelist (
    whitelist_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    source VARCHAR(50) DEFAULT 'manual',
    note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    burned_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(user_id)
);

-- Method 1: If you have a list of user IDs
-- Replace these with your actual user IDs
INSERT INTO whitelist (user_id, source, note, created_at)
VALUES
    -- Admins/Owners (keep these forever)
    (306145881, 'owner', 'Bot owner - permanent access', NOW()),
    
    -- Example members (replace with your actual member IDs)
    -- (123456789, 'initial_import', 'Existing member', NOW()),
    -- (987654321, 'initial_import', 'Existing member', NOW()),
    -- (456789123, 'initial_import', 'Existing member', NOW()),
    
    -- Add more members here...
    
    (0, 'placeholder', 'Remove this line', NOW())  -- Remove this placeholder
ON CONFLICT (user_id) DO NOTHING;

-- Method 2: If members are already in users table (from previous bot activity)
-- This whitelists everyone who interacted with the bot before deployment
/*
INSERT INTO whitelist (user_id, source, note, created_at)
SELECT 
    user_id,
    'grandfathered',
    'Existing user - grandfathered in',
    NOW()
FROM users
WHERE created_at < '2024-01-15'  -- Set to your deployment date
ON CONFLICT (user_id) DO NOTHING;
*/

-- Method 3: Whitelist specific usernames (if you have a list)
/*
WITH username_list AS (
    SELECT unnest(ARRAY[
        'username1',
        'username2',
        'username3'
    ]) as username
)
INSERT INTO whitelist (user_id, source, note, created_at)
SELECT 
    u.user_id,
    'username_import',
    'Imported by username: ' || u.username,
    NOW()
FROM users u
JOIN username_list ul ON u.username = ul.username
ON CONFLICT (user_id) DO NOTHING;
*/

-- Verify the import
SELECT 
    COUNT(*) as total_whitelisted,
    COUNT(CASE WHEN source = 'initial_import' THEN 1 END) as imported,
    COUNT(CASE WHEN source = 'owner' THEN 1 END) as owners,
    COUNT(CASE WHEN burned_at IS NOT NULL THEN 1 END) as already_used
FROM whitelist;

-- List all whitelisted users (for verification)
SELECT 
    user_id,
    source,
    note,
    created_at,
    CASE 
        WHEN burned_at IS NOT NULL THEN 'Used'
        WHEN expires_at < NOW() THEN 'Expired'
        ELSE 'Active'
    END as status
FROM whitelist
ORDER BY created_at DESC
LIMIT 50;