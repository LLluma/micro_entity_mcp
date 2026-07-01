import os
import re


def sanitize_segment(name: str) -> str:
    text = name.lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = text.strip("-._")
    text = text.replace("..", "-")
    if text in (".", "..") or text == "":
        return ""
    return text


def resolve_segment(*, explicit: str | None, workspace: str | None) -> str | None:
    if explicit is not None:
        slug = sanitize_segment(explicit)
        if slug:
            return slug
    if workspace is not None:
        slug = sanitize_segment(os.path.basename(workspace.rstrip("/")))
        if slug:
            return slug
    return None
