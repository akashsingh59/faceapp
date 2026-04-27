ALTER TABLE photos
    DROP CONSTRAINT IF EXISTS photos_status_check;

ALTER TABLE photos
    ADD COLUMN content_type text,
    ADD COLUMN size_bytes bigint,
    ADD COLUMN upload_mode text,
    ADD COLUMN upload_started_at timestamptz,
    ADD COLUMN uploaded_at timestamptz,
    ADD COLUMN upload_error_code text,
    ADD COLUMN upload_error_message text;

UPDATE photos
SET
    status = 'uploaded',
    size_bytes = COALESCE(size_bytes, 1),
    upload_mode = COALESCE(upload_mode, 'single_put'),
    uploaded_at = COALESCE(uploaded_at, created_at)
WHERE status IN ('uploaded', 'indexed');

UPDATE photos
SET
    status = 'upload_failed',
    size_bytes = COALESCE(size_bytes, 1),
    upload_mode = COALESCE(upload_mode, 'single_put')
WHERE status = 'failed';

ALTER TABLE photos
    ALTER COLUMN size_bytes SET NOT NULL,
    ALTER COLUMN upload_mode SET NOT NULL;

ALTER TABLE photos
    ADD CONSTRAINT photos_size_bytes_check CHECK (size_bytes > 0),
    ADD CONSTRAINT photos_upload_mode_check CHECK (upload_mode IN ('single_put', 'multipart')),
    ADD CONSTRAINT photos_status_check
        CHECK (status IN ('pending_upload', 'uploading', 'uploaded', 'upload_failed', 'upload_aborted')),
    ADD CONSTRAINT photos_uploaded_at_status_check
        CHECK (
            (status = 'uploaded' AND uploaded_at IS NOT NULL)
            OR (status <> 'uploaded')
        );

CREATE TABLE photo_upload_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    photo_id uuid NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    upload_mode text NOT NULL,
    s3_multipart_upload_id text,
    part_size_bytes bigint,
    part_count integer,
    status text NOT NULL,
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT photo_upload_sessions_upload_mode_check
        CHECK (upload_mode IN ('single_put', 'multipart')),
    CONSTRAINT photo_upload_sessions_status_check
        CHECK (status IN ('active', 'completed', 'aborted', 'expired', 'failed')),
    CONSTRAINT photo_upload_sessions_mode_upload_id_check
        CHECK (
            (upload_mode = 'multipart' AND s3_multipart_upload_id IS NOT NULL)
            OR (upload_mode = 'single_put' AND s3_multipart_upload_id IS NULL)
        ),
    CONSTRAINT photo_upload_sessions_part_count_check
        CHECK (part_count IS NULL OR part_count > 0),
    CONSTRAINT photo_upload_sessions_part_size_check
        CHECK (part_size_bytes IS NULL OR part_size_bytes > 0)
);

CREATE INDEX photo_upload_sessions_photo_id_status_idx
    ON photo_upload_sessions (photo_id, status);

CREATE INDEX photo_upload_sessions_event_id_status_idx
    ON photo_upload_sessions (event_id, status);

CREATE UNIQUE INDEX photo_upload_sessions_one_active_per_photo_idx
    ON photo_upload_sessions (photo_id)
    WHERE status = 'active';

CREATE INDEX photos_event_id_status_created_at_idx
    ON photos (event_id, status, created_at DESC);
