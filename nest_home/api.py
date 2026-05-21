"""nest_home public API — the attention engine entrypoints called by the page.

Design promises honoured here:
  * Performance — bounded queries (limit per source), one pass per category.
    The page calls get_attention(["A"]) first so List A paints instantly, then
    get_attention(["B","C"]) to fill the rest behind it.
  * Every whitelisted method returns a TRUTHY payload, so the client-side
    success branch (`if (r.message)`) always fires. See CoWork_Helper gotcha
    2026-05-13 (whitelisted-action-needs-return-value).

Role-based views (v0.0.3): a "Nest Home Layout" record decides which lists and
which quick-launch buttons a user sees. Resolution order:
    1. a layout attached to the user's Role Profile
    2. a layout attached to one of the user's Roles
    3. no layout  -> sensible defaults (managers A+B+C, everyone else A)
Highest `priority` wins inside each step.
"""

import json
import frappe

from nest_home.attention.sources import todos, awaiting

# Roles that see the full A+B+C management board when NO layout matches the
# user. Everyone else defaults to List A only.
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


def _user_role_profiles(user):
    """Role profiles assigned to the user. Handles both the long-standing single
    field (role_profile_name) and, defensively, a multi-profile child table if
    the site has one. Never raises."""
    profiles = set()
    try:
        udoc = frappe.get_cached_doc("User", user)
    except Exception:
        return profiles
    rp = getattr(udoc, "role_profile_name", None)
    if rp:
        profiles.add(rp)
    # Newer Frappe allows multiple role profiles via a child table; the row
    # fieldname has varied across versions, so probe a couple defensively.
    try:
        for row in (udoc.get("role_profiles") or []):
            val = getattr(row, "role_profile", None) or getattr(row, "role_profile_name", None)
            if val:
                profiles.add(val)
    except Exception:
        pass
    return profiles


def _pick_layout(filters):
    """Return the highest-priority enabled layout matching filters, or None."""
    try:
        rows = frappe.get_all(
            "Nest Home Layout",
            filters=filters,
            fields=["name", "priority"],
            order_by="priority desc, modified desc",
            limit_page_length=1,
        )
    except Exception:
        return None
    if not rows:
        return None
    try:
        return frappe.get_cached_doc("Nest Home Layout", rows[0]["name"])
    except Exception:
        return None


def resolve_layout(user=None):
    """The single source of truth for 'which layout does this user get?'.
    Role Profile match wins over Role match. Returns a Layout doc or None."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return None

    profiles = _user_role_profiles(user)
    if profiles:
        layout = _pick_layout({
            "enabled": 1,
            "applies_to": "Role Profile",
            "role_profile": ["in", list(profiles)],
        })
        if layout:
            return layout

    roles = _user_roles(user)
    if roles:
        layout = _pick_layout({
            "enabled": 1,
            "applies_to": "Role",
            "role": ["in", list(roles)],
        })
        if layout:
            return layout
    return None


def user_has_layout(user=None):
    """Cheap boolean used by the landing redirect."""
    return resolve_layout(user) is not None


def lists_for_user(user=None):
    """Which categories this user should see. A matching layout decides;
    otherwise managers default to A+B+C and everyone else to List A."""
    user = user or frappe.session.user
    layout = resolve_layout(user)
    if layout:
        mapped = set()
        if getattr(layout, "show_list_a", 0):
            mapped.add("A")
        if getattr(layout, "show_list_b", 0):
            mapped.add("B")
        if getattr(layout, "show_list_c", 0):
            mapped.add("C")
        return [c for c in _VALID_CATEGORIES if c in mapped] or ["A"]

    # No layout -> sensible defaults.
    if _user_roles(user) & _DEFAULT_MANAGER_ROLES:
        return ["A", "B", "C"]
    return ["A"]


def _tile_payload(doc):
    return {
        "label": doc.label,
        "icon": doc.icon or "octicon octicon-rocket",
        "icon_image": getattr(doc, "icon_image", None) or "",
        "route": doc.route or "",
        "color": getattr(doc, "color", None) or "",
        "description": getattr(doc, "description", None) or "",
        "sort_order": doc.sort_order or 0,
    }


def _layout_tiles(layout):
    """Buttons chosen on the layout, in the admin's drag order. Skips buttons
    that have been disabled in the shared library."""
    out = []
    for row in (layout.get("tiles") or []):
        name = getattr(row, "tile", None)
        if not name:
            continue
        try:
            doc = frappe.get_cached_doc("Nest Home Tile", name)
        except Exception:
            continue
        if not getattr(doc, "enabled", 1):
            continue
        out.append(_tile_payload(doc))
    return out


def _default_tiles(roles):
    """Fallback when no layout: enabled library tiles filtered by allowed_roles
    (no allowed_roles = visible to all), sorted."""
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
        return out
    for name in names:
        doc = frappe.get_cached_doc("Nest Home Tile", name)
        allowed_roles = [r.role for r in (doc.get("allowed_roles") or [])]
        if allowed_roles and not (set(allowed_roles) & roles):
            continue
        out.append(_tile_payload(doc))
    return out


def tiles_for_user(user=None):
    """Buttons for this user: the layout's chosen buttons if a layout matches,
    otherwise the role-filtered library default."""
    user = user or frappe.session.user
    layout = resolve_layout(user)
    if layout:
        return _layout_tiles(layout)
    return _default_tiles(_user_roles(user))


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


def _show_nest_credit(s):
    """Show the NestERP credit unless an admin has explicitly turned it off."""
    if not s:
        return True
    val = getattr(s, "show_nest_credit", None)
    return True if val is None else bool(val)


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
    """Role/layout-aware quick-launch buttons for the current user."""
    return {"tiles": tiles_for_user(frappe.session.user)}


@frappe.whitelist()
def get_landing_context():
    """One call the page makes on load: config + buttons, so the shell can paint
    before the attention lists arrive. Always truthy."""
    user = frappe.session.user
    s = _settings()
    layout = resolve_layout(user)

    greeting = ""
    if layout and getattr(layout, "greeting", None):
        greeting = layout.greeting
    elif s and getattr(s, "greeting", None):
        greeting = s.greeting

    return {
        "user": user,
        "user_fullname": frappe.utils.get_fullname(user),
        "allowed_lists": lists_for_user(user),
        "logo_url": _logo_url(),
        "app_title": (getattr(s, "app_title", None) if s else None) or "Nest Home",
        "tiles": tiles_for_user(user),
        "greeting": greeting,
        "has_layout": layout is not None,
        "show_nest_credit": _show_nest_credit(s),
        "support_link": (getattr(s, "support_link", None) if s else None) or "",
    }
