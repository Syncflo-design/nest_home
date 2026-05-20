"""nest_home public API — the attention engine entrypoints called by the page.

Design promises honoured here:
  * Performance — bounded queries (limit per source), one pass per category.
    The page calls get_attention(["A"]) first so List A paints instantly, then
    get_attention(["B","C"]) to fill the rest behind it.
  * Every whitelisted method returns a TRUTHY payload, so the client-side
    success branch (`if (r.message)`) always fires. See CoWork_Helper gotcha
    2026-05-13 (whitelisted-action-needs-return-value).
"""

import json
import frappe

from nest_home.attention.sources import todos, awaiting

# Roles that see the full A+B+C management board when Settings has no explicit
# per-role mapping. Everyone else defaults to List A only.
_DEFAULT_MANAGER_ROLES = {
    "System Manager", "Sales Manager", "Purchase Manager",
    "Stock Manager", "Manufacturing Manager", "Accounts Manager",
}

_VALID_CATEGORIES = ("A", "B", "C")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _coerce_categories(categories):
    """frappe.call may deliver a list as a JSON string. Normalise to a clean
    list of valid category codes."""
    if categories is None:
        return list(_VALID_CATEGORIES)
    if isinstance(categories, str):
        try:
            categories = json.loads(categories)
        except Exception:
            categories = [c.strip() for c in categories.split(",")]
    if not isinstance(categories, (list, tuple)):
        categories = [categories]
    return [c for c in categories if c in _VALID_CATEGORIES] or list(_VALID_CATEGORIES)


def _settings():
    try:
        return frappe.get_cached_doc("Nest Home Settings")
    except Exception:
        return None


def _user_roles(user):
    return set(frappe.get_roles(user))


def lists_for_user(user=None):
    """Which categories this user's roles should see — union across roles.
    Reads Nest Home Settings.role_lists child table if configured; otherwise
    falls back to: manager roles → A+B+C, everyone else → A."""
    user = user or frappe.session.user
    roles = _user_roles(user)
    s = _settings()

    mapped = set()
    has_config = False
    if s and getattr(s, "role_lists", None):
        for row in s.role_lists:
            if row.role in roles:
                has_config = True
                if getattr(row, "show_list_a", 0):
                    mapped.add("A")
                if getattr(row, "show_list_b", 0):
                    mapped.add("B")
                if getattr(row, "show_list_c", 0):
                    mapped.add("C")

    if has_config:
        # Preserve canonical A,B,C order
        return [c for c in _VALID_CATEGORIES if c in mapped] or ["A"]

    # No explicit config for any of this user's roles → sensible defaults.
    if roles & _DEFAULT_MANAGER_ROLES:
        return ["A", "B", "C"]
    return ["A"]


def _logo_url():
    """Nest Home Settings.brand_logo wins; else nest_theme's customer_logo; else
    None (the page supplies its own default)."""
    s = _settings()
    if s and getattr(s, "brand_logo", None):
        return s.brand_logo
    try:
        nt = frappe.get_cached_doc("Nest Theme Settings")
        if getattr(nt, "customer_logo", None):
            return nt.customer_logo
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Whitelisted endpoints
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_attention(categories=None, limit_per=20):
    """Return normalised attention items for the requested categories.

    categories: list/JSON-string subset of ["A","B","C"]; defaults to all the
    current user is entitled to. limit_per bounds each source."""
    user = frappe.session.user
    limit_per = int(limit_per or 20)
    requested = _coerce_categories(categories)
    allowed = set(lists_for_user(user))
    cats = [c for c in requested if c in allowed]

    result = {"user": user, "A": [], "B": [], "C": [], "counts": {}}
    if "A" in cats:
        result["A"] = todos.list_a(user, limit_per)
    if "C" in cats:
        result["C"] = todos.list_c(user, limit_per)
    if "B" in cats:
        result["B"] = awaiting.list_b(user, limit_per)

    result["counts"] = {k: len(result[k]) for k in _VALID_CATEGORIES}
    result["allowed_lists"] = sorted(allowed)
    return result


@frappe.whitelist()
def get_tiles():
    """Role-aware quick-launch tiles. Returns enabled Nest Home Tile records the
    user is allowed to see (no allowed_roles = visible to all), sorted."""
    user = frappe.session.user
    roles = _user_roles(user)
    out = []
    try:
        names = frappe.get_all(
            "Nest Home Tile",
            filters={"enabled": 1},
            pluck="name",
            order_by="sort_order asc, label asc",
            limit_page_length=200,
        )
    except Exception:
        return {"tiles": []}

    for name in names:
        doc = frappe.get_cached_doc("Nest Home Tile", name)
        allowed_roles = [r.role for r in (doc.get("allowed_roles") or [])]
        if allowed_roles and not (set(allowed_roles) & roles):
            continue
        out.append({
            "label": doc.label,
            "icon": doc.icon or "octicon octicon-rocket",
            "icon_image": getattr(doc, "icon_image", None) or "",
            "route": doc.route or "",
            "color": getattr(doc, "color", None) or "",
            "description": getattr(doc, "description", None) or "",
            "sort_order": doc.sort_order or 0,
        })
    return {"tiles": out}


@frappe.whitelist()
def get_landing_context():
    """One call the page makes on load: config + tiles, so the shell can paint
    before the attention lists arrive. Always truthy."""
    user = frappe.session.user
    s = _settings()
    return {
        "user": user,
        "user_fullname": frappe.utils.get_fullname(user),
        "allowed_lists": lists_for_user(user),
        "logo_url": _logo_url(),
        "app_title": (getattr(s, "app_title", None) if s else None) or "Nest Home",
        "tiles": get_tiles().get("tiles", []),
        "greeting": (getattr(s, "greeting", None) if s else None) or "",
    }
