"""The keystone: one normalised item schema every attention source emits.

Getting this shape right means future sources plug in without touching the
page. Every source returns a list of dicts produced by `make_item`.

Schema
------
    list_category : "A" | "B" | "C" | "notif"
    title         : str   primary line (ToDo description / "SO-00012 — Acme")
    subtitle      : str   secondary context (party, assigned-by, item summary)
    deep_link     : list  frappe.set_route args, e.g. ["Form", "ToDo", name]
    source_doctype: str
    source_name   : str
    priority      : "High" | "Medium" | "Low" | None  (normalised)
    date          : "YYYY-MM-DD" | None   (due / transaction date)
    age_days      : int   whole days since `created` (for the "3d" badge + sort)
    owner_or_party: str | None  counterparty / who it concerns
    status        : str   source status
    meta          : dict  source-specific extras (qty, amount, currency, ...)
"""

import frappe
from frappe.utils import getdate, nowdate, cint


_PRIORITY_MAP = {
    "high": "High", "urgent": "High", "1": "High",
    "medium": "Medium", "med": "Medium", "2": "Medium",
    "low": "Low", "3": "Low",
}


def normalise_priority(value):
    """Map any source priority into High/Medium/Low or None."""
    if value is None:
        return None
    return _PRIORITY_MAP.get(str(value).strip().lower(), str(value))


def age_days(created):
    """Whole days between `created` and today. Tolerant of None/str/datetime."""
    if not created:
        return 0
    try:
        c = getdate(created)
        return max(0, (getdate(nowdate()) - c).days)
    except Exception:
        return 0


def make_item(
    list_category,
    title,
    deep_link,
    source_doctype,
    source_name,
    subtitle="",
    priority=None,
    date=None,
    created=None,
    owner_or_party=None,
    status=None,
    meta=None,
):
    """Build one normalised attention item. The single shape every source emits."""
    return {
        "list_category": list_category,
        "title": (title or "").strip() or source_name,
        "subtitle": (subtitle or "").strip(),
        "deep_link": deep_link or [],
        "source_doctype": source_doctype,
        "source_name": source_name,
        "priority": normalise_priority(priority),
        "date": str(date) if date else None,
        "age_days": age_days(created or date),
        "owner_or_party": owner_or_party,
        "status": status,
        "meta": meta or {},
    }


def plain_text(html):
    """Strip HTML to plain text without depending on frappe.utils.strip_html
    (absent in some v16 builds). Cheap server-side fallback."""
    if not html:
        return ""
    try:
        from frappe.utils import strip_html_tags
        return (strip_html_tags(html) or "").strip()
    except Exception:
        import re
        return re.sub(r"<[^>]+>", "", str(html)).strip()
