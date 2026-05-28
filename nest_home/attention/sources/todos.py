"""List A (My Activities) and List C (Waiting On Others) — both from the ToDo
table, different filters. A and C are nearly free: one bounded query each.

List A: ToDos allocated to me, Open                 → "do these".
List C: ToDos I assigned to others (not me), Open   → "chase these".

Lead/Customer-linked ToDos are the primary signal for sales/presales seats, so
those rows are enriched: the raw reference (CRM-LEAD-0007) is resolved to the
party's real name, and the row deep-links to the party — the Party Activity Hub
(`/app/party-activity/<type>/<name>`) if nest_crm_tasks is installed, otherwise
the Lead/Customer record. Enrichment is a single batched lookup per doctype and
runs as the session user, so names only resolve if the user may read them.
"""

import frappe
from nest_home.attention.schema import make_item, plain_text

# Fields safe to request from ToDo via the ORM as the session user.
_TODO_FIELDS = [
    "name", "description", "date", "priority", "status",
    "allocated_to", "assigned_by", "owner", "creation",
    "reference_type", "reference_name",
]

# Party doctypes we resolve to a friendly display name + which fields to pull.
_PARTY_ENRICH = {
    "Lead":     ["lead_name", "company_name"],
    "Customer": ["customer_name"],
}


def _party_hub_available():
    """True if the nest_crm_tasks Party Activity Hub page is installed."""
    try:
        return bool(frappe.db.exists("Page", "party-activity"))
    except Exception:
        return False


def _build_party_lookups(rows):
    """One batched get_list per party doctype, keyed by name. Runs as the
    session user (no ignore_permissions) so names only resolve if readable."""
    by_type = {}
    for t in rows:
        rt, rn = t.get("reference_type"), t.get("reference_name")
        if rt in _PARTY_ENRICH and rn:
            by_type.setdefault(rt, set()).add(rn)

    lookups = {}
    for dt, names in by_type.items():
        try:
            recs = frappe.get_list(
                dt,
                filters=[["name", "in", list(names)]],
                fields=["name"] + _PARTY_ENRICH[dt],
                limit_page_length=0,
            )
            lookups[dt] = {r["name"]: r for r in recs}
        except Exception:
            lookups[dt] = {}
    return lookups


def _party_display(dt, rn, rec):
    if not rec:
        return rn
    if dt == "Lead":
        name = rec.get("lead_name") or ""
        company = rec.get("company_name") or ""
        if name and company:
            return name + " — " + company
        return name or company or rn
    if dt == "Customer":
        return rec.get("customer_name") or rn
    return rn


def _party_contact_company(dt, rec):
    """Split a party record into (contact, company) for filtering + sorting.
    Lead -> (lead_name, company_name); Customer -> ("", customer_name)."""
    if not rec:
        return "", ""
    if dt == "Lead":
        return rec.get("lead_name") or "", rec.get("company_name") or ""
    if dt == "Customer":
        return "", rec.get("customer_name") or ""
    return "", ""


def _deep_link(t, has_hub):
    rt, rn = t.get("reference_type"), t.get("reference_name")
    if rt in _PARTY_ENRICH and rn:
        if has_hub:
            return ["party-activity", rt, rn]   # nest_crm_tasks hub
        return ["Form", rt, rn]                 # the Lead/Customer record
    return ["Form", "ToDo", t.get("name")]      # plain task → the ToDo form


def _todo_item(t, category, who_label, who_value, lookups, has_hub):
    title = plain_text(t.get("description")) or t.get("name")
    rt, rn = t.get("reference_type"), t.get("reference_name")

    party_display = None
    contact = ""
    company = ""
    bits = []
    if rt in _PARTY_ENRICH and rn:
        rec = (lookups.get(rt) or {}).get(rn)
        party_display = _party_display(rt, rn, rec)
        contact, company = _party_contact_company(rt, rec)
        bits.append("{0}: {1}".format(rt, party_display))
    elif rt and rn:
        bits.append("{0} {1}".format(rt, rn))
    if who_value:
        bits.append("{0} {1}".format(who_label, who_value))

    return make_item(
        list_category=category,
        title=title,
        subtitle="  ·  ".join(bits),
        deep_link=_deep_link(t, has_hub),
        source_doctype="ToDo",
        source_name=t.get("name"),
        priority=t.get("priority"),
        date=t.get("date"),
        created=t.get("creation"),
        owner_or_party=party_display or who_value,
        status=t.get("status") or "Open",
        meta={
            "reference_type": rt,
            "reference_name": rn,
            "party": party_display,
            "contact": contact,
            "company": company,
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
    lookups = _build_party_lookups(rows)
    has_hub = _party_hub_available()
    return [
        _todo_item(t, "A", "From", t.get("assigned_by") or t.get("owner"), lookups, has_hub)
        for t in rows
    ]


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
    lookups = _build_party_lookups(rows)
    has_hub = _party_hub_available()
    return [
        _todo_item(t, "C", "Waiting on", t.get("allocated_to"), lookups, has_hub)
        for t in rows
    ]
