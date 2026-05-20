# nest_home — Claude session notes

A reusable **NestERP standard** Frappe v16 app: a role-based, branded landing
page built on *push, not pull* — the user's work is on screen at login.

> Built on the same desk-Page bundle pattern as `nest_crm_mobile` /
> `nest_crm_tasks`. Before touching `.js` / `.html` / `.json` in
> `nest_home/nest_home/page/nest_home/`, re-read these CoWork_Helper gotchas:
> `2026-05-10-frappe-v16-page-api-drift.md` (mount in `page.body`, it is jQuery),
> `2026-05-11-*listview*` (build Pages, not listview hooks),
> `2026-05-13-frappe-whitelisted-action-needs-return-value.md` (return truthy),
> `2026-05-17-cowork-write-tool-silent-truncation.md` (write big files via bash
> heredoc; verify with `wc -c` / `node --check`).

## The five non-negotiables (page-bundle pattern)

1. Page HTML is assembled in `nest_home.js` as a **string array joined with
   `\n`**, not a backtick template literal.
2. `nest_home.html` is a **placeholder only** (`<div id="nest-home-placeholder">`)
   — no apostrophes (Frappe registers it as a single-quoted template).
3. The controller is reachable as `window.nestHome` (class instance), mounted
   into `page.body` via `$('<div>').appendTo(page.body)` — never
   `$(wrapper).find('.x')`.
4. Deploy cycle: push → Frappe Cloud Bench → **Pull Updates** → Deploy →
   incognito reload. Bump `BUILD_MARKER` (in `nest_home.js`) and `__version__`
   each deploy.
5. CSS lives in a **separate file** (`public/css/nest_home.css`) loaded via a
   `<link>` from the page JS — keeps JS under the ~20KB Cowork write cap.

## Architecture

- **Attention engine** (`nest_home/api.py` + `attention/`): one whitelisted
  `get_attention(categories)` that aggregates pluggable sources and normalises
  every item to ONE schema (`attention/schema.py::make_item`). New source =
  new function returning that shape; the page never changes.
  - List A / C: `attention/sources/todos.py` (ToDo table, different filters).
  - List B: `attention/sources/awaiting.py` — **rules table** `AWAITING_RULES`.
    v1 rule = Draft (docstatus 0) docs the user can submit, for Sales Order /
    Purchase Order / Work Order. Add a doctype = append a rule dict.
- **Item schema (keystone):** `list_category, title, subtitle, deep_link
  (frappe.set_route args array), source_doctype, source_name, priority, date,
  age_days, owner_or_party, status, meta`.
- **Page** paints List A first (`get_attention(["A"])`), then B/C behind it.
  Freshness v1 = load + manual Refresh + quiet 2-min visible-tab poll. Live
  socket push is phase 2 (see realtime-timing gotcha).
- **Doctypes:** `Nest Home Settings` (Single — default landing, allow override,
  brand logo, per-role list map child table) and `Nest Home Tile` (data-driven
  quick-launch; admins add a tile by creating a record).
- **Branding:** `Nest Home Settings.brand_logo` wins, else `nest_theme`'s
  `Nest Theme Settings.customer_logo`; CSS reuses nest_theme palette vars.
- **Landing resolution** (`boot.py`): user preference → role default → app
  default, via the `get_website_user_home_page` hook. Per-user *workspace* API
  is blocked (gotcha 2026-05-07) so we use the home-page hook, not workspaces.

## Open item to verify on first deploy

Does v16 consult `get_website_user_home_page` for **desk** users (not just
portal)? If not, the per-user override needs a small boot-time redirect shim;
role_home_page still covers managers. Record the answer here after smoke test.

## Repo / site

- GitHub: `Syncflo-design/nest_home` (org for NestERP apps)
- Site: `Syncflo_internal_V16` — route `/desk/nest-home`
- Module: `Nest Home`
