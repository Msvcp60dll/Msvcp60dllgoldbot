-- Migration: Initialize star_tx_cursor table
-- This ensures the reconciliation cursor has an initial record

-- Insert initial cursor record if it doesn't exist
INSERT INTO star_tx_cursor (id, last_tx_at, updated_at)
VALUES (
    1, 
    NOW() - INTERVAL '7 days',  -- Look back 7 days initially
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- Verify the record exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM star_tx_cursor WHERE id = 1) THEN
        RAISE EXCEPTION 'Failed to initialize star_tx_cursor';
    END IF;
END $$;