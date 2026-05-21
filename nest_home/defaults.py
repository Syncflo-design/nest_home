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
    # Use an explicit, deterministic name and bypass the naming series. The
    # fixture buttons (NEST-TILE-0001..) were imported with fixed names without
    # advancing the series counter, so a series-named insert would collide.
    doc.name = "NEST-TILE-WS-" + frappe.scrub(label).upper()
    doc.flags.name_set = True
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


# ---------------------------------------------------------------------------
# Reusable: compile a Role Profile's view in one call
# ---------------------------------------------------------------------------
def _resolve_tile_spec(spec, sort_order=0):
    """Turn one tile spec into a shared-library Nest Home Tile name.

    A spec is either:
      * str  -> an existing tile's *name* (e.g. "NEST-TILE-0007") or its *label*
                (e.g. "CRM"). Must already exist.
      * dict -> {"label", "route", "icon"?, "color"?, "sort_order"?}; the library
                tile is reused if one with that label exists, else created (matched
                by label, so re-runs never duplicate). "label" + "route" required.
    """
    if isinstance(spec, str):
        if frappe.db.exists("Nest Home Tile", spec):
            return spec
        by_label = frappe.db.get_value("Nest Home Tile", {"label": spec}, "name")
        if by_label:
            return by_label
        frappe.throw(
            "No Nest Home Tile named or labelled '{0}'. Pass a dict with "
            "label + route to create it.".format(spec)
        )
    if isinstance(spec, dict):
        label = spec.get("label")
        route = spec.get("route")
        if not label or not route:
            frappe.throw("A tile dict needs at least 'label' and 'route'.")
        return _ensure_tile(
            label,
            route,
            spec.get("icon") or "octicon octicon-rocket",
            spec.get("color") or "",
            spec.get("sort_order", sort_order),
        )
    frappe.throw("Each tile must be a string (name/label) or a dict.")


def ensure_layout_for_profile(
    role_profile,
    tiles,
    lists=("A", "B", "C"),
    greeting="Here's what needs you today.",
    priority=0,
    enabled=1,
    layout_name=None,
    replace_tiles=True,
):
    """Create or update the Nest Home Layout for a Role Profile, in one call.

    This is the scripted path for "compile a view per Role Profile": point it at
    a role profile and the buttons you want; it ensures every shared-library tile
    exists (no duplicates) and wires them onto the layout in the given order.
    Idempotent — safe to call again to reshape an existing layout.

    role_profile : name of an existing Role Profile (the layout's match key).
    tiles        : ordered list of tile specs (see _resolve_tile_spec).
    lists        : subset of {"A","B","C"} the layout shows (default: all).
    greeting     : header greeting line.
    priority     : higher wins when a user matches more than one layout.
    enabled      : 0/1.
    layout_name  : document name to use (defaults to the role profile name).
    replace_tiles: True rewrites the tile rows to exactly `tiles`; False appends
                   only the missing ones to whatever the layout already has.

    Returns the layout document name.
    """
    if not _doctypes_ready():
        frappe.throw("nest_home doctypes are not migrated yet.")
    if not role_profile:
        frappe.throw("role_profile is required.")

    # Resolve buttons to library tile names first (creating dict specs as needed).
    tile_names = [_resolve_tile_spec(spec, i) for i, spec in enumerate(tiles or [])]

    existing = frappe.db.get_value(
        "Nest Home Layout",
        {"applies_to": "Role Profile", "role_profile": role_profile},
        "name",
    )
    if existing:
        doc = frappe.get_doc("Nest Home Layout", existing)
    else:
        doc = frappe.new_doc("Nest Home Layout")
        doc.layout_name = layout_name or role_profile

    doc.enabled = 1 if enabled else 0
    doc.applies_to = "Role Profile"
    doc.role_profile = role_profile
    doc.priority = priority
    doc.greeting = greeting
    lset = set(lists or ())
    doc.show_list_a = 1 if "A" in lset else 0
    doc.show_list_b = 1 if "B" in lset else 0
    doc.show_list_c = 1 if "C" in lset else 0

    if replace_tiles:
        doc.set("tiles", [])
    have = {row.tile for row in (doc.get("tiles") or [])}
    for name in tile_names:
        if name not in have:
            doc.append("tiles", {"tile": name})
            have.add(name)

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    return doc.name
