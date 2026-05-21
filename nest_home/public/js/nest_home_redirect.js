// Make nest-home the user's desk "home".
//
// The server sets frappe.boot.nest_home_landing ONLY when a layout matches this
// user (and also sets it as boot.home_page). This script is the belt-and-braces
// layer: whenever the desk routes to its empty/home landing — initial load, a
// refresh, or the Home/house button — we send the user to nest-home. Clicking a
// specific workspace or opening a record/list still works, because those routes
// are non-empty and are left alone.

frappe.provide("nest_home");

(function () {
	function target() {
		return frappe.boot && frappe.boot.nest_home_landing;
	}

	function redirect_if_home() {
		try {
			var t = target();
			if (!t) return;
			var r = frappe.get_route() || [];
			// Empty route == the desk's home landing.
			var is_home = r.length === 0 || (r.length === 1 && (r[0] === "" || r[0] == null));
			if (is_home && (r[0] || "") !== t) {
				frappe.set_route(t);
			}
		} catch (e) {
			/* never break the desk */
		}
	}

	function bind_router() {
		if (frappe.router && frappe.router.on) {
			// Fires on every route change — catches the Home/house button.
			frappe.router.on("change", redirect_if_home);
			return true;
		}
		return false;
	}

	// Initial landing (router may already be settled by the time we run).
	$(document).on("app_ready", function () {
		redirect_if_home();
		bind_router();
	});
	// Safety nets for timing.
	setTimeout(function () { redirect_if_home(); bind_router(); }, 800);
	setTimeout(redirect_if_home, 2000);
})();
