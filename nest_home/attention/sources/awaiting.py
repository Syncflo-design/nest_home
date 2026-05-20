"""List B — 'Awaiting My Action': documents in a state needing a decision from
the user's seat.

This is the extensible part. Rather than hardcode three doctypes, List B is
driven by a table of RULES. Each rule says: which doctype, what state counts as
"awaiting action", which permission gates it, and how to render title/subtitle.
Adding a new source later = appending a rule dict (or, eventually, a
"Nest Home Awaiting Rule" doctype that feeds this same shape).

v1 rule for all three sources: a document is "awaiting my action" when it is a
DRAFT (docstatus = 0) and the current user holds SUBMIT permission on that
doctype — i.e. it is sitting on their desk waiting for them to approve/submit.
Read-level row permissions are applied automatically by frappe.get_list run as
the session user, so users only ever see drafts they're allowed to see.
"""

import frappe
from nest_home.attention.schema import make_item


# ---------------------------------------------------------------------------
# RULES — the config surface. Append a dict to add a doctype to List B.
# ---------------------------------------------------------------------------
#   doctype      : the document type to scan
#   gate_ptype   : permission the user must hold for this source to apply
#   docstatus    : which docstatus counts as "awaiting" (0 = Draft for v1)
#   party_field  : fieldname of the counterparty (shown in subtitle)
#   date_field   : fieldname of the transaction/posting date
#   amount_field : optional fieldname of a total to surface in meta
#   label        : human label for the source (used in subtitle prefix)
# ---------------------------------------------------------------------------
AWAITING_RULES = [
    {
        "doctype": "Sales Order",
        "gate_ptype": "submit",
        "docstatus": 0,
        "party_field": "customer",
        "date_field": "transaction_date",
        "amount_field": "grand_total",
        "currency_field": "currency",
        "label": "Sales Order",
    },
    {
        "doctype": "Purchase Order",
        "gate_ptype": "submit",
        "docstatus": 0,
        "party_field": "supplier",
        "date_field": "transaction_date",
        "amount_field": "grand_total",
        "currency_field": "currency",
        "label": "Purchase Order",
    },
    {
        "doctype": "Work Order",
        "gate_ptype": "submit",
        "docstatus": 0,
        "party_field": "production_item",
        "date_field": "planned_start_date",
        "amount_field": "qty",
        "currency_field": None,
        "label": "Work Order",
    },
]


def _rule_items(rule, user, limit):
    dt = rule["doctype"]

    # Source-level gate: skip the whole doctype if the user can't act on it.
    # has_permission with the submit ptype is doctype-level — cheap, no query.
    if not frappe.has_permission(dt, ptype=rule.get("gate_ptype", "submit"), user=user):
        return []

    # Build the field list defensively — only request fields that exist on the
    # doctype, so a rule never blows up on a site missing an optional column.
    meta = frappe.get_meta(dt)
    wanted = ["name", "status", "creation", "owner"]
    for key in ("party_field", "date_field", "amount_field", "currency_field"):
        f = rule.get(key)
        if f and meta.has_field(f):
            wanted.append(f)
    wanted = list(dict.fromkeys(wanted))  # de-dupe, keep order

    rows = frappe.get_list(
        dt,
        filters={"docstatus": rule.get("docstatus", 0)},
        fields=wanted,
        order_by="modified desc",
        limit_page_length=limit,
        # run as the session user so READ row-permissions apply automatically
    )

    items = []
    for r in rows:
        party = r.get(rule.get("party_field") or "") or ""
        title = "{0} — {1}".format(r.get("name"), party) if party else r.get("name")
        amount = r.get(rule.get("amount_field") or "")
        currency = r.get(rule.get("currency_field") or "") if rule.get("currency_field") else ""
        sub = rule["label"] + " · Draft awaiting your submission"
        items.append(
            make_item(
                list_category="B",
                title=title,
                subtitle=sub,
                deep_link=["Form", dt, r.get("name")],
                source_doctype=dt,
                source_name=r.get("name"),
                priority=None,
                date=r.get(rule.get("date_field") or ""),
                created=r.get("creation"),
                owner_or_party=party or None,
                status=r.get("status") or "Draft",
                meta={
                    "amount": amount,
                    "currency": currency,
                    "rule": rule["label"],
                },
            )
        )
    return items


def list_b(user, limit=20):
    """Aggregate every rule into a single List B, bounded per source."""
    out = []
    for rule in AWAITING_RULES:
        try:
            out.extend(_rule_items(rule, user, limit))
        except Exception:
            # A rule must never break the whole board — e.g. a doctype not
            # installed on this site (Work Order without Manufacturing) can make
            # get_meta / has_permission / get_list raise. Skip that source.
            continue
    # Most recent first across all sources; cap the combined list too.
    out.sort(key=lambda i: i.get("date") or "", reverse=True)
    return out[: limit * 2]
