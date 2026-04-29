import re


def make_safe_export_basename(name: str | None, fallback: str = "assessment") -> str:
    value = (name or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return normalized or fallback
