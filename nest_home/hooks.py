app_name        = "nest_home"
app_title       = "Nest Home"
app_publisher   = "NestERP / Syncflo"
app_description = "Role-based, branded landing page with a push-not-pull attention engine and data-driven quick-launch tiles."
app_email       = "ops@syncflo.co.za"
app_license     = "MIT"
app_icon        = "octicon octicon-home"

# ---------------------------------------------------------------------------
# Landing-page resolution (push, not pull).
#
# Order of precedence honoured by nest_home.boot.get_user_home_page:
#   1. the user's own "Preferred Landing Page" (if overrides are allowed)
#   2. their role default (role_home_page below)
#   3. the app default from Nest Home Settings
#
# role_home_page is also declared so the framework still has a sensible answer
# if the per-user hook is ever bypassed. Per-user *workspace* overrides are NOT
# attempted — that API is blocked for admins acting on other users (see
# CoWork_Helper gotchas/2026-05-07-frappe-workspace-per-user-api-blocked.md).
# ---------------------------------------------------------------------------
role_home_page = {
    "System Manager":        "nest-home",
    "Sales Manager":         "nest-home",
    "Purchase Manager":      "nest-home",
    "Stock Manager":         "nest-home",
    "Manufacturing Manager": "nest-home",
    "Accounts Manager":      "nest-home",
}

# Resolves the final landing page per user. Returning None lets the framework
# fall through to role_home_page. (This hook is consulted in get_home_page.)
get_website_user_home_page = "nest_home.boot.get_user_home_page"

# On login, bust the per-user home_page cache so the resolver re-runs.
on_session_creation = "nest_home.boot.on_session_creation"

# ---------------------------------------------------------------------------
# Fixtures shipped with the app.
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
app_include_js  = []
app_include_css = []
