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

// One-click Home in the page title bar, in front of the page title, on every
// desk page (forms, lists, reports, workspaces). They all build their header in
// frappe.ui.Page.make, so we wrap that; pages built before this file ran are
// covered on app_ready. The button goes to the user's own landing from boot.py
// (nest-home, or a layout's route Landing Page, which boot keeps out of
// home_page), otherwise to Frappe's own home_page.
(function () {
	var CLS = "nest-home-btn";

	function go_home() {
		frappe.set_route(frappe.boot.nest_home_landing || frappe.boot.home_page || "");
	}

	function add_style() {
		if (document.getElementById("nest-home-btn-style")) return;
		$("<style id='nest-home-btn-style'></style>").text([
			".page-title ." + CLS + "{display:flex;align-items:center;justify-content:center;",
			"flex-shrink:0;width:28px;height:28px;margin-right:var(--margin-sm);",
			"border-radius:var(--border-radius-md);cursor:pointer;--icon-stroke:var(--gray-700)}",
			".page-title ." + CLS + ":hover{background:var(--fg-hover-color)}",
			"[data-theme=dark] .page-title ." + CLS + "{--icon-stroke:var(--gray-300)}"
		].join("")).appendTo("head");
	}

	function add_home_buttons(root) {
		try {
			$(root).find(".page-head .page-title").each(function () {
				var $title = $(this);
				if ($title.children("." + CLS).length) return;
				add_style();
				var $btn = $("<button type='button' class='btn-reset " + CLS + "'></button>")
					.attr({ title: __("Home"), "aria-label": __("Home") })
					.html(frappe.utils.icon("house", "md"))
					.on("click", go_home);
				var $toggle = $title.children(".sidebar-toggle-btn").first();
				if ($toggle.length) $btn.insertAfter($toggle);
				else $btn.prependTo($title);
			});
		} catch (e) {
			/* never break the desk */
		}
	}

	if (frappe.ui.Page && frappe.ui.Page.prototype.make) {
		var make = frappe.ui.Page.prototype.make;
		frappe.ui.Page.prototype.make = function () {
			var result = make.apply(this, arguments);
			add_home_buttons(this.wrapper);
			return result;
		};
	}

	$(document).on("app_ready", function () {
		add_home_buttons(document.body);
	});
})();
