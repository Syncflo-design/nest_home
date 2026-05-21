"""Per-user landing-page resolution for nest_home.

The product principle is "push, not pull": when a user logs in, the page that
already shows their work should be the front door. As of v0.0.3 the redirect to
nest-home is gated on the user actually having a Nest Home Layout that matches
their Role Profile or Role -- if they don't, they are left on the standard desk.

Precedence:
    1. the user's own Preferred Landing Page  (if overrides are allowed)
    2. nest-home                               (ONLY if a layout matches them)
    3. the app default                         (Nest Home Settings.default_landing)

get_user_home_page is wired as the get_website_user_home_page hook; despite the
name it is consulted in Frappe's get_home_page() resolution. Returning None lets
the framework fall through to the standard desk.
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
    default_label = (getattr(s, "default_landing", None) if s else None) or "Standard Desk"

    # 1. explicit user preference always wins (including a deliberate "Standard
    #    Desk" choice, which means "leave me on the desk").
    if allow_override:
        try:
            pref = frappe.db.get_value("User", user, "preferred_landing_page")
        except Exception:
            pref = None
        if pref:
            return _route_for_label(pref)

    # 2. nest-home, but ONLY if a layout actually matches this user.
    try:
        from nest_home.api import user_has_layout
        if user_has_layout(user):
            return "nest-home"
    except Exception:
        pass

    # 3. app-wide fallback for users with no layout (defaults to standard desk).
    return _route_for_label(default_label)


def boot_session(bootinfo):
    """Publish this user's resolved landing route to the desk so the
    client-side redirect (nest_home_redirect.js) can act on it. Set only when
    a layout matches the user (or they have an explicit preference); left
    unset otherwise, so those users simply stay on the standard desk."""
    try:
        landing = _resolve_landing(frappe.session.user)
        if landing:
            bootinfo["nest_home_landing"] = landing
            # Make the desk Home/house button land here too (it normally
            # points at the default workspace).
            bootinfo["home_page"] = landing
    except Exception:
        pass


def get_user_home_page(user):
    """Hook entrypoint. Returns a route string, or None to fall through."""
    try:
        return _resolve_landing(user)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "nest_home.get_user_home_page")
        return None


def on_session_creation(login_manager=None):
    """Bust the per-user home_page cache on login so the resolver re-runs (e.g.
    after the user changes their preference, gets a new layout, or after a
    deploy)."""
    try:
        user = frappe.session.user
        cache = frappe.cache()
        cache.hdel("home_page", user)
    except Exception:
        pass
