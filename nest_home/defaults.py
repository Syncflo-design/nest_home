"""Default seed data for nest_home.

ensure_admin_layout() ships the out-of-the-box experience: a System Manager
layout that mirrors the conventional desk's main workspaces as quick-launch
buttons, displayed in the nest_home layout. Wired as after_install AND
after_migrate so a fresh deploy gives every admin a ready-made landing page.

Idempotent: it does nothing once the "Administrator" layout exists, so any admin
edits (or a deliberate delete-and-rebuild) are preserved across later deploys.
"""

import frappe

ADMIN_LAYOUT_NAME = "Administrator"

# Mirrors the main desk workspaces. (label, workspace route slug, icon, colour)
_ADMIN_TILES = [
    ("Selling",           "selling",           "fa fa-shopping-cart", "#6b85a3"),
    ("Buying",            "buying",            "fa fa-shopping-bag",  "#b08968"),
    ("Stock",             "stock",             "fa fa-cubes",         "#82a085"),
    ("Invoicing",         "invoicing",         "fa fa-file-text-o",   "#7a8aa0"),
    ("Financial Reports", "financial-reports", "fa fa-bar-chart",     "#5b7a99"),
    ("CRM",               "crm",               "fa fa-users",         "#9a7aa0"),
    ("Manufacturing",     "manufacturing",     "fa fa-industry",      "#a08a6b"),
    ("Assets",            "assets",            "fa fa-cube",          "#6b9a8a"),
    ("Projects",          "projects",          "fa fa-tasks",         "#8a8a6b"),
    ("Support",           "support",           "fa fa-life-ring",     "#a07a7a"),
    ("Users",             "users",             "fa fa-user",          "#6b85a3"),
    ("Website",           "website",           "fa fa-globe",         "#5b9aa0"),
    ("Settings",          "erpnext-settings",  "fa fa-cog",           "#7a7a8a"),
]


def _doctypes_ready():
    """Guard so this never explodes if called before the schema is synced."""
    try:
        return bool(
            frappe.db.exists("DocType", "Nest Home Layout")
            and frappe.db.exists("DocType", "Nest Home Tile")
        )
    except Exception:
        return False


def _ensure_tile(label, route, icon, color, sort_order):
    """Return the name of the library button with this label, creating it if
    absent. Matching by label keeps re-runs from making duplicates."""
    name = frappe.db.get_value("Nest Home Tile", {"label": label}, "name")
    if name:
        return name
    doc = frappe.get_doc({
        "doctype": "Nest Home Tile",
        "label": label,
        "enabled": 1,
        "icon": icon,
        "color": color,
        "route": route,
        "sort_order": sort_order,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def ensure_admin_layout():
    """Create the default System Manager layout once. No-op if it exists."""
    try:
        if not _doctypes_ready():
            return
        if frappe.db.exists("Nest Home Layout", ADMIN_LAYOUT_NAME):
            return

        tile_rows = []
        for i, (label, route, icon, color) in enumerate(_ADMIN_TILES):
            tile_rows.append({"tile": _ensure_tile(label, route, icon, color, i)})

        frappe.get_doc({
            "doctype": "Nest Home Layout",
            "layout_name": ADMIN_LAYOUT_NAME,
            "enabled": 1,
            "applies_to": "Role",
            "role": "System Manager",
            "priority": 0,
            "show_list_a": 1,
            "show_list_b": 1,
            "show_list_c": 1,
            "greeting": "Here's what needs you today.",
            "tiles": tile_rows,
        }).insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        frappe.log_error(frappe.get_traceback(), "nest_home.ensure_admin_layout")
