CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    collection_id text NOT NULL UNIQUE,
    status text NOT NULL DEFAULT 'created',
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT events_status_check
        CHECK (status IN ('created', 'processing', 'ready', 'failed')),
    CONSTRAINT events_slug_check
        CHECK (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$')
);

CREATE TABLE photos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    s3_key text NOT NULL,
    filename text NOT NULL,
    status text NOT NULL DEFAULT 'uploaded',
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT photos_event_id_id_unique UNIQUE (event_id, id),
    CONSTRAINT photos_event_id_s3_key_unique UNIQUE (event_id, s3_key),
    CONSTRAINT photos_status_check
        CHECK (status IN ('uploaded', 'indexed', 'failed'))
);

CREATE INDEX photos_event_id_created_at_idx
    ON photos (event_id, created_at DESC);

CREATE TABLE persons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    face_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT persons_event_id_id_unique UNIQUE (event_id, id),
    CONSTRAINT persons_event_id_face_id_unique UNIQUE (event_id, face_id)
);

CREATE INDEX persons_event_id_created_at_idx
    ON persons (event_id, created_at DESC);

CREATE TABLE photo_faces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    photo_id uuid NOT NULL,
    person_id uuid NOT NULL,
    similarity numeric(5,2) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT photo_faces_event_photo_fk
        FOREIGN KEY (event_id, photo_id)
        REFERENCES photos(event_id, id)
        ON DELETE CASCADE,
    CONSTRAINT photo_faces_event_person_fk
        FOREIGN KEY (event_id, person_id)
        REFERENCES persons(event_id, id)
        ON DELETE CASCADE,
    CONSTRAINT photo_faces_photo_id_person_id_unique UNIQUE (photo_id, person_id),
    CONSTRAINT photo_faces_similarity_check
        CHECK (similarity >= 0 AND similarity <= 100)
);

CREATE INDEX photo_faces_person_id_created_at_idx
    ON photo_faces (person_id, created_at DESC);

CREATE INDEX photo_faces_event_id_person_id_idx
    ON photo_faces (event_id, person_id);

CREATE TABLE client_searches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    matched_person_id uuid,
    similarity numeric(5,2),
    status text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT client_searches_event_person_fk
        FOREIGN KEY (event_id, matched_person_id)
        REFERENCES persons(event_id, id)
        ON DELETE SET NULL (matched_person_id),
    CONSTRAINT client_searches_status_check
        CHECK (status IN ('completed', 'no_match', 'failed')),
    CONSTRAINT client_searches_similarity_check
        CHECK (similarity IS NULL OR (similarity >= 0 AND similarity <= 100)),
    CONSTRAINT client_searches_completed_match_check
        CHECK (
            (status = 'completed' AND matched_person_id IS NOT NULL AND similarity IS NOT NULL)
            OR (status IN ('no_match', 'failed') AND matched_person_id IS NULL AND similarity IS NULL)
        )
);

CREATE INDEX client_searches_event_id_created_at_idx
    ON client_searches (event_id, created_at DESC);

CREATE INDEX client_searches_matched_person_id_idx
    ON client_searches (matched_person_id)
    WHERE matched_person_id IS NOT NULL;
