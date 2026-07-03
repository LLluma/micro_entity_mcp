"""Issue profile server — exposes issue tracking via FastMCP."""

import re

_issue_id_re = re.compile(r"^[Ii][Ss][Ss][Uu][Ee]-?(\d+)$")


def _normalize_issue_id(raw: str) -> str:
    """Canonicalize *raw* to ``ISSUE-NNNN`` form.

    All-digits strings are treated as a bare ordinal (``"7"`` -> ``"ISSUE-0007"``).
    Any casing of ``ISSUE``, optionally followed by ``-``, then digits, is
    normalised (e.g. ``"issue-7"``, ``"Issue7"`` -> ``"ISSUE-0007"``).
    Anything else is returned unchanged.

    Idempotent: ``_normalize_issue_id(_normalize_issue_id(s)) == _normalize_issue_id(s)``.
    """
    if raw.isdigit():
        return f"ISSUE-{int(raw):04d}"
    m = _issue_id_re.match(raw)
    if m:
        return f"ISSUE-{int(m.group(1)):04d}"
    return raw
