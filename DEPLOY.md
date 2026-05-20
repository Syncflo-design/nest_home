# Deploying nest_home to Frappe Cloud

Site: `Syncflo_internal_V16` (`syncflo-internal.c.frappe.cloud` / `www.nesterp.co.za`).

## 1. Create the GitHub repo + push (run on your machine)

The Cowork sandbox has no GitHub credentials, so the first push is manual. From
`C:\ClaudeCode\nest_home` (the repo is already initialised and committed):

```bash
# create the empty repo on github.com under Syncflo-design first (UI or gh), then:
git remote add origin https://github.com/Syncflo-design/nest_home.git
git branch -M main
git push -u origin main
```

## 2. Frappe Cloud Bench

1. Bench → **Apps → Add App → From GitHub** → `Syncflo-design/nest_home`, branch `main`.
2. Wait for the green build.
3. Bench → **Pull Updates** (do NOT skip — picks up the latest commit).
4. Bench → **Deploy**.
5. Sites → `Syncflo_internal_V16` → **Apps → Install** → pick `nest_home`.

## 3. Verify (incognito)

1. Open an incognito window, log in, go to `/app/nest-home`.
2. Console should show: `Nest Home loaded: v0.0.1-2026-05-20-initial` (the BUILD_MARKER).
3. List A (My Activities) should paint first; B/C fill behind it.
4. Quick-launch tiles render (seeded defaults gated by role).
5. As a manager (e.g. System Manager) you should land on `/app/nest-home` after login.

## 4. Per-user override smoke test

1. Open **User** for a test user → set **Preferred Landing Page** = "Standard Desk".
2. Log in as that user → they should NOT be forced to nest-home.
3. Set it back to "Nest Home" → they land on nest-home.

NOTE: the per-user override is wired via the `get_website_user_home_page` hook.
If it turns out v16 only consults that hook for website (portal) users and not
desk users, the role default (`role_home_page`) still applies; we then add a
small boot-time redirect. **Verify this behaviour on the first deploy** and
record the result in CLAUDE.md.

## Bump the BUILD_MARKER every deploy

`nest_home/nest_home/page/nest_home/nest_home.js` → `BUILD_MARKER` constant.
Also bump `nest_home/nest_home/__init__.py` `__version__`.
