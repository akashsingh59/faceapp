ALTER TABLE events
    DROP CONSTRAINT IF EXISTS events_status_check;

ALTER TABLE events
    ADD CONSTRAINT events_status_check
        CHECK (status IN ('created', 'queued', 'processing', 'ready', 'failed', 'processing_failed'));
