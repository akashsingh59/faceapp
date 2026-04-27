from pathlib import Path
import os


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def database_mode() -> str:
    return "postgres" if database_url() else "memory"


def bool_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}


def int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as error:
        raise ValueError(f"Environment variable {name} must be an integer") from error


def upload_multipart_threshold_bytes() -> int:
    return int_env("UPLOAD_MULTIPART_THRESHOLD_BYTES", 25 * 1024 * 1024)


def upload_multipart_part_size_bytes() -> int:
    return int_env("UPLOAD_MULTIPART_PART_SIZE_BYTES", 8 * 1024 * 1024)


def upload_url_expires_seconds() -> int:
    return int_env("UPLOAD_URL_EXPIRES_SECONDS", 900)


def upload_max_batch_files() -> int:
    return int_env("UPLOAD_MAX_BATCH_FILES", 100)


def upload_max_file_size_bytes() -> int:
    return int_env("UPLOAD_MAX_FILE_SIZE_BYTES", 100 * 1024 * 1024)


load_env_file()
