# nest_home

A reusable **NestERP standard** custom Frappe v16 app: a role-based, branded
landing page built on the principle *push, not pull* — when a user logs in,
the things needing their attention are already on screen. They should not have
to go looking for their work.

## Two zones on every landing page

1. **Quick-launch** — large, attractive, data-driven tiles to that role's
   most-used functions (admin-configured via `Nest Home Tile`, no code change
   to add one).
2. **Attention lists** — live per-user worklists, populated on landing:
   * **List A — My Activities** — ToDos allocated to me, status Open.
   * **List B — Awaiting My Action** — documents needing a decision from my
     seat (v1: Work / Purchase / Sales Orders in Draft that I can submit).
     Built as extensible rules, so more doctypes plug in without page changes.
   * **List C — Waiting On Others** — ToDos I assigned to other people, Open.

## The attention engine

One server-side aggregator (`nest_home.api.get_attention`) pulls from pluggable
sources and normalises every item to a single schema, so future sources plug in
without touching the page:

```
{ list_category, title, subtitle, deep_link, source_doctype, source_name,
  priority, date, age_days, owner_or_party, status, meta }
```

## Configurability

* Role-based shell via `role_home_page` in `hooks.py`.
* Per-user landing override (curated Select on User) honoured by a login hook,
  falling back to role default → app default.
* `Nest Home Settings` (Single) — app-wide config: default landing, whether
  users may override, brand logo, which lists each role shows.
* `Nest Home Tile` — data-driven quick-launch; admins add a tile by creating a
  record.

## Branding

Aligns with `nest_theme`: reuses its CSS palette tokens, and uses the
`Nest Home Settings` logo if set, otherwise `nest_theme`'s `syn_logo_url`.

Site: `Syncflo_internal_V16` (`www.nesterp.co.za`). Route: `/desk/nest-home`.
