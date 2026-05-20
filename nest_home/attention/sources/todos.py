"""List A (My Activities) and List C (Waiting On Others) — both from the ToDo
table, different filters. A and C are nearly free: one bounded query each.

List A: ToDos allocated to me, Open                 → "do these".
List C: ToDos I assigned to others (not me), Open   → "chase these".
"""

import frappe
from nest_home.attention.schema import make_item, plain_text

# Fields safe to request from ToDo via the ORM as the session user.
_TODO_FIELDS = [
    "name", "description", "date", "priority", "status",
    "allocated_to", "assigned_by", "owner", "creation",
    "reference_type", "reference_name",
]


def _todo_item(t, category, who_label, who_value):
    """Shared builder for an A or C row."""
    title = plain_text(t.get("description")) or t.get("name")
    ref_t = t.get("reference_type")
    ref_n = t.get("reference_name")
    bits = []
    if who_value:
        bits.append("{0}: {1}".format(who_label, who_value))
    if ref_t and ref_n:
        bits.append("{0} {1}".format(ref_t, ref_n))
    subtitle = "  ·  ".join(bits)

    return make_item(
        list_category=category,
        title=title,
        subtitle=subtitle,
        deep_link=["Form", "ToDo", t.get("name")],
        source_doctype="ToDo",
        source_name=t.get("name"),
        priority=t.get("priority"),
        date=t.get("date"),
        created=t.get("creation"),
        owner_or_party=who_value,
        status=t.get("status") or "Open",
        meta={
            "reference_type": ref_t,
            "reference_name": ref_n,
        },
    )


def list_a(user, limit=20):
    """List A — ToDos allocated to me, Open. 'Do these.'"""
    rows = frappe.get_list(
        "ToDo",
        filters={"allocated_to": user, "status": "Open"},
        fields=_TODO_FIELDS,
        order_by="date asc, modified desc",
        limit_page_length=limit,
        ignore_permissions=True,  # a user may always see ToDos allocated to them
    )
    return [_todo_item(t, "A", "From", t.get("assigned_by") or t.get("owner")) for t in rows]


def list_c(user, limit=20):
    """List C — ToDos I assigned to OTHERS (not myself), still Open. 'Chase these.'"""
    rows = frappe.get_list(
        "ToDo",
        filters=[
            ["assigned_by", "=", user],
            ["allocated_to", "!=", user],
            ["status", "=", "Open"],
        ],
        fields=_TODO_FIELDS,
        order_by="date asc, modified desc",
        limit_page_length=limit,
        ignore_permissions=True,  # I assigned them, so I'm allowed to track them
    )
    return [_todo_item(t, "C", "Waiting on", t.get("allocated_to")) for t in rows]
