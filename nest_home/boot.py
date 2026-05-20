"""Per-user landing-page resolution for nest_home.

The product principle is "push, not pull": when a user logs in, the page that
already shows their work should be the front door. This module decides which
page that is, honouring the precedence chain:

    1. the user's own Preferred Landing Page  (if overrides are allowed)
    2. their role default                      (hooks.role_home_page)
    3. the app default                         (Nest Home Settings.default_landing)

get_user_home_page is wired as the get_website_user_home_page hook; despite the
name it is consulted in Frappe's get_home_page() resolution. Returning None lets
the framework fall through to role_home_page.
"""

import frappe

# Curated Select label -> desk page route. "" means "use the standard desk"
# (return None so the framework default workspace is shown).
LANDING_ROUTES = {
    "Nest Home":     "nest-home",
    "CRM Mobile":    "crm-mobile",
    "My Activities": "my-activities",
    "Standard Desk": "",
}

# Mirrors hooks.role_home_page. Kept here so step 2 of the chain can run inside
# this single resolver (which wins over the framework's own role lookup).
_ROLE_HOME = {
    "System Manager":        "nest-home",
    "Sales Manager":         "nest-home",
    "Purchase Manager":      "nest-home",
    "Stock Manager":         "nest-home",
    "Manufacturing Manager": "nest-home",
    "Accounts Manager":      "nest-home",
}


def _settings():
    try:
        return frappe.get_cached_doc("Nest Home Settings")
    except Exception:
        return None


def _route_for_label(label):
    """Map a Select label to a route. Unknown / 'Standard Desk' -> None."""
    if not label:
        return None
    route = LANDING_ROUTES.get(label)
    return route or None  # "" or None -> None (standard desk)


def _resolve_landing(user):
    if not user or user == "Guest":
        return None

    s = _settings()
    allow_override = bool(getattr(s, "allow_user_override", 1)) if s else True
    default_label = (getattr(s, "default_landing", None) if s else None) or "Nest Home"

    # 1. user preference
    if allow_override:
        try:
            pref = frappe.db.get_value("User", user, "preferred_landing_page")
        except Exception:
            pref = None
        if pref:
            # An explicit "Standard Desk" choice means "leave me on the desk".
            return _route_for_label(pref)

    # 2. role default
    roles = set(frappe.get_roles(user))
    for role, route in _ROLE_HOME.items():
        if role in roles:
            return route

    # 3. app default
    return _route_for_label(default_label)


def get_user_home_page(user):
    """Hook entrypoint. Returns a route string, or None to fall through."""
    try:
        return _resolve_landing(user)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "nest_home.get_user_home_page")
        return None


def on_session_creation(login_manager=None):
    """Bust the per-user home_page cache on login so the resolver re-runs (e.g.
    after the user changes their preference or after a deploy)."""
    try:
        user = frappe.session.user
        cache = frappe.cache()
        # Frappe caches the resolved home page per user under this hash key.
        cache.hdel("home_page", user)
    except Exception:
        pass
