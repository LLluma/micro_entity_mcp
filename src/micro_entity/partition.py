import re


def sanitize_segment(name: str) -> str:
    text = name.lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = text.strip("-._")
    text = text.replace("..", "-")
    if text in (".", "..") or text == "":
        return ""
    return text
