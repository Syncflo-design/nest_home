app_name        = "nest_home"
app_title       = "Nest Home"
app_publisher   = "NestERP / Syncflo"
app_description = "Role-based, branded landing page with a push-not-pull attention engine and data-driven quick-launch tiles."
app_email       = "ops@syncflo.co.za"
app_license     = "MIT"
app_icon        = "octicon octicon-home"

# ---------------------------------------------------------------------------
# Landing-page resolution (push, not pull) — v0.0.3 is layout-driven.
#
# A user is redirected to nest-home ONLY when a Nest Home Layout matches their
# Role Profile or one of their Roles. Order of precedence honoured by
# nest_home.boot.get_user_home_page:
#   1. the user's own "Preferred Landing Page" (if overrides are allowed)
#   2. nest-home, but ONLY if a layout matches them
#   3. the app default from Nest Home Settings (defaults to the standard desk)
#
# role_home_page is intentionally EMPTY: redirecting by role alone would send
# users to nest-home even with no layout configured, which contradicts the
# "only if a layout exists" rule. The dynamic hook below is the single
# authority. Per-user *workspace* overrides are NOT attempted — that API is
# blocked for admins acting on other users (see CoWork_Helper gotchas
# 2026-05-07-frappe-workspace-per-user-api-blocked.md).
# ---------------------------------------------------------------------------
role_home_page = {}

# Resolves the final landing page per user. Returning None lets the framework
# fall through to the standard desk. (This hook is consulted in get_home_page.)
get_website_user_home_page = "nest_home.boot.get_user_home_page"

# On login, bust the per-user home_page cache so the resolver re-runs.
on_session_creation = "nest_home.boot.on_session_creation"
boot_session = "nest_home.boot.boot_session"

# Seed the default 'Administrator' (System Manager) layout on install and on
# every migrate. Idempotent — see nest_home.defaults.
after_install = [
    "nest_home.defaults.ensure_admin_layout",
    "nest_home.defaults.ensure_standard_tiles",
]
after_migrate = [
    "nest_home.defaults.ensure_admin_layout",
    "nest_home.defaults.ensure_standard_tiles",
]

# ---------------------------------------------------------------------------
# Fixtures shipped with the app.
#
# Nest Home Layout records are deliberately NOT fixtured: they are site-specific
# config the admin creates, and shipping them would overwrite local layouts on
# migrate. Only the seed buttons and the User custom fields travel with the app.
# ---------------------------------------------------------------------------
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["name", "in", [
            "User-nest_home_section",
            "User-preferred_landing_page",
        ]]],
    },
    {
        "doctype": "Nest Home Tile",
        "filters": [["name", "like", "NEST-TILE-%"]],
    },
]

# No global desk bundle — the page loads its own CSS via a <link> tag.
app_include_js  = ["/assets/nest_home/js/nest_home_redirect.js"]
app_include_css = []
