-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Full-text search trigger for listings
CREATE OR REPLACE FUNCTION listings_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'B') ||
        setweight(to_tsvector('russian', coalesce(NEW.address, '')), 'C') ||
        setweight(to_tsvector('russian', coalesce(NEW.city, '')), 'C');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger fires on INSERT and UPDATE
-- (will be created after alembic runs the table DDL)
-- It's safe to run this after tables exist:
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'listings') THEN
        DROP TRIGGER IF EXISTS tsvector_update ON listings;
        CREATE TRIGGER tsvector_update
            BEFORE INSERT OR UPDATE ON listings
            FOR EACH ROW EXECUTE FUNCTION listings_search_vector_update();
    END IF;
END;
$$;
