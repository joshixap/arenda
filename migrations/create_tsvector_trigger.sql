-- Run this once after tables are created (e.g., via alembic or lifespan)
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

DROP TRIGGER IF EXISTS tsvector_update ON listings;
CREATE TRIGGER tsvector_update
    BEFORE INSERT OR UPDATE ON listings
    FOR EACH ROW EXECUTE FUNCTION listings_search_vector_update();
