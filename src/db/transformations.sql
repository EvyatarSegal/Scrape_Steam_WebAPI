-- Flatten JSON Data
-- This view parses the raw JSON from Steam and SteamSpy into a clean analytics table.

DROP VIEW IF EXISTS etl_v_game_analytics CASCADE;

CREATE OR REPLACE VIEW etl_v_game_analytics AS -- Redefine View to include new cols
WITH parsed_data AS (
    SELECT
        appid,
        COALESCE(steamspy_data->>'name', steam_store_data->>'name') as name,
        steamspy_data->>'developer' as developer,
        steamspy_data->>'publisher' as publisher,
        steam_store_data->'genres'->0->>'description' as genre_primary,
        COALESCE(
            CAST(steam_store_data->'price_overview'->>'initial' AS FLOAT) / 100.0,
            CAST(NULLIF(steamspy_data->>'price', '') AS FLOAT) / 100.0
        ) as price_initial,
        CAST(steam_store_data->'price_overview'->>'final' AS FLOAT) / 100.0 as price_final,
        CAST(steam_store_data->'price_overview'->>'discount_percent' AS FLOAT) as discount_percent,
        CASE 
            WHEN steam_store_data->'release_date'->>'date' ~ '^[A-Z][a-z]{2} \d{1,2}, \d{4}$' 
            THEN TO_DATE(steam_store_data->'release_date'->>'date', 'Mon DD, YYYY')
            ELSE NULL 
        END as release_date,
        steamspy_data->>'owners' as owners_range,
        CAST(NULLIF(steamspy_data->>'ccu', '') AS INTEGER) as ccu,
        CAST(NULLIF(steamspy_data->>'positive', '') AS INTEGER) as positive_reviews,
        CAST(NULLIF(steamspy_data->>'negative', '') AS INTEGER) as negative_reviews,
        (
            CASE WHEN json_typeof(steamspy_data->'tags') = 'object' 
            THEN (SELECT array_agg(key) FROM json_each(steamspy_data->'tags'))
            ELSE NULL END
        ) as tags,
        
        -- New Columns (Hardware & Age)
        CAST(NULLIF(REGEXP_REPLACE(steam_store_data->>'required_age', '[^0-9]', '', 'g'), '') AS INTEGER) as required_age,
        steam_store_data->'pc_requirements'->>'minimum' as pc_req_min,
        steam_store_data->'pc_requirements'->>'recommended' as pc_req_rec,
        
        -- New Columns (Counts & features)
        -- Languages: Count commas + 1. If null, 0.
        CASE 
            WHEN steam_store_data->>'supported_languages' IS NULL THEN 0
            ELSE array_length(string_to_array(steam_store_data->>'supported_languages', ','), 1)
        END as languages_count,
        
        CAST(steam_store_data->'achievements'->>'total' AS INTEGER) as achievement_count,
        
        -- DLC Count Safe Check
        CASE WHEN json_typeof(steam_store_data->'dlc') = 'array'
             THEN json_array_length(steam_store_data->'dlc')
             ELSE 0
        END as dlc_count,
        
        -- Booleans
        CAST(steam_store_data->>'is_free' AS BOOLEAN) as is_free,
        (steam_store_data->>'controller_support' = 'full') as controller_support,
        
        -- Safe Check for Genres
        CASE WHEN json_typeof(steam_store_data->'genres') = 'array' THEN
            EXISTS (
                SELECT 1 
                FROM json_array_elements(steam_store_data->'genres') AS g 
                WHERE g->>'description' = 'Early Access'
            )
        ELSE FALSE END as is_early_access,
        
        -- Steam Deck is usually in 'categories'. ID 1 means Multi-player etc. 
        -- Deck Verified is complex category ID, skipping specific check for now or defaulting False
        -- until we map the ID.
        FALSE as steam_deck,
        
        -- Peak CCU (Placeholder until we have a source or use ccu as peak)
        CAST(NULLIF(steamspy_data->>'ccu', '') AS INTEGER) as peak_ccu
        
    FROM raw_game_data
    WHERE steamspy_data IS NOT NULL
),
owners_calc AS (
    SELECT 
        *,
        CAST(REPLACE(SPLIT_PART(owners_range, ' .. ', 1), ',', '') AS BIGINT) as owners_min,
        CAST(REPLACE(SPLIT_PART(owners_range, ' .. ', 2), ',', '') AS BIGINT) as owners_max,
        (CAST(REPLACE(SPLIT_PART(owners_range, ' .. ', 1), ',', '') AS BIGINT) + CAST(REPLACE(SPLIT_PART(owners_range, ' .. ', 2), ',', '') AS BIGINT)) / 2 as owners_midpoint
    FROM parsed_data
),
final_calc AS (
    SELECT
        *,
        CASE 
            WHEN publisher ILIKE '%Electronic Arts%' OR publisher ILIKE '%Ubisoft%' OR publisher ILIKE '%Activision%' OR publisher ILIKE '%Bethesda%' OR publisher ILIKE '%Rockstar%' OR publisher ILIKE '%2K%' OR publisher ILIKE '%Sony%' OR publisher ILIKE '%Microsoft%' OR publisher ILIKE '%Nintendo%' OR publisher ILIKE '%Square Enix%' OR publisher ILIKE '%Capcom%' OR publisher ILIKE '%Bandai Namco%' OR publisher ILIKE '%Sega%' OR publisher ILIKE '%Konami%' OR publisher ILIKE '%Take-Two%' OR publisher ILIKE '%Warner Bros%' 
            THEN 'AAA'
            WHEN price_initial > 20 AND owners_midpoint > 100000 
            THEN 'AA'
            ELSE 'Indie'
        END as publisher_tier
    FROM owners_calc
)
SELECT * FROM final_calc;


CREATE OR REPLACE PROCEDURE refresh_analytics()
LANGUAGE plpgsql
AS $$
BEGIN
    TRUNCATE TABLE game_analytics;
    INSERT INTO game_analytics (
        appid, name, genre_primary, developer, publisher, publisher_tier,
        price_initial, price_final, discount_percent, release_date,
        owners_min, owners_max, owners_midpoint,
        positive_reviews, negative_reviews, tags, ccu,
        required_age, pc_req_min, pc_req_rec,
        languages_count, achievement_count, dlc_count,
        is_free, controller_support, is_early_access, steam_deck, peak_ccu
    )
    SELECT 
        appid, name, genre_primary, developer, publisher, publisher_tier,
        price_initial, price_final, discount_percent, release_date,
        owners_min, owners_max, owners_midpoint,
        positive_reviews, negative_reviews, tags, ccu,
        required_age, pc_req_min, pc_req_rec,
        languages_count, achievement_count, dlc_count,
        is_free, controller_support, is_early_access, steam_deck, peak_ccu
    FROM etl_v_game_analytics;
END;
$$;
