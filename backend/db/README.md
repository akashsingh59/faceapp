# Database

Postgres schema changes live in `migrations/` as ordered SQL files.

Run migrations in filename order against the application database. This keeps
the backend source focused on API code while giving the database a stable home
that can later be wired into Alembic, Flyway, or another migration runner.
