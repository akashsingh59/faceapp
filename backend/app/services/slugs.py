import re
from uuid import uuid4


def make_slug(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    base = cleaned or "event"
    return f"{base}-{uuid4().hex[:6]}"
