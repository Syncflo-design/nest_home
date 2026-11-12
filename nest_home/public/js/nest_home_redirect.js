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

	// "Home" is the bare desk address (/desk, or the old /app), read from the address
	// bar. frappe.get_route() is not enough: from Frappe 16.56 it briefly reads empty
	// while a full page load settles a deep link, which bounced every bookmark, email
	// link and refresh to the landing page.
	function at_desk_root() {
		var p = (window.location.pathname || "").replace(/\/+$/, "");
		return p === "/desk" || p === "/app";
	}

	function redirect_if_home() {
		try {
			var t = target();
			if (t && at_desk_root()) frappe.set_route(t);
		} catch (e) {
			/* never break the desk */
		}
	}

	// The desk renders an empty route (the breadcrumb Home icon links to /desk) by
	// loading a desk *Page* named frappe.boot.home_page. A layout Landing Page that
	// is a route (e.g. query-report/Project Tracker) is not a Page, so send the
	// empty route straight to it instead of asking the server for that Page (403).
	function patch_home_render() {
		var pv = frappe.views && frappe.views.pageview;
		if (!pv || pv.nest_home_patched) return;
		var original = pv.show;
		pv.show = function (name) {
			var t = target();
			if (!name && t && t.indexOf("/") !== -1) {
				// Off the desk root an empty route is only a passing state on load.
				if (at_desk_root()) frappe.set_route(t);
				return;
			}
			return original.apply(this, arguments);
		};
		pv.nest_home_patched = true;
	}
	patch_home_render();

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
		patch_home_render();
		redirect_if_home();
		bind_router();
	});
	// Safety nets for timing.
	setTimeout(function () { redirect_if_home(); bind_router(); }, 800);
	setTimeout(redirect_if_home, 2000);
})();
