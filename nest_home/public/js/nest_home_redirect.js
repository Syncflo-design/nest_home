// Layout-gated landing redirect for desk users.
//
// Frappe does not reliably send desk users to a custom page at login via the
// home_page hooks, so we enforce it client-side. The server sets
// frappe.boot.nest_home_landing ONLY when a layout matches this user (honouring
// their personal landing preference too). On the first desk load of the
// session, if we're sitting on the default landing — not a record/list/report
// the user deliberately opened — we hop to that page. Never breaks the desk.

frappe.provide("nest_home");

(function () {
	var DEEP = ["form", "list", "report", "query-report", "dashboard-view",
	            "print", "tree", "kanban", "gantt", "calendar"];

	function maybe_redirect() {
		try {
			var target = frappe.boot && frappe.boot.nest_home_landing;
			if (!target) return;
			if (sessionStorage.getItem("nest_home_landed")) return;

			var r = (frappe.get_route && frappe.get_route()) || [];
			var first = (r[0] || "").toString().toLowerCase();

			// Already on the target page — just remember and stop.
			if (first === target.toLowerCase()) {
				sessionStorage.setItem("nest_home_landed", "1");
				return;
			}

			// Mark as handled so we only ever do this once per session.
			sessionStorage.setItem("nest_home_landed", "1");

			// If the user deep-linked into a specific record/view, leave them be.
			if (DEEP.indexOf(first) >= 0) return;

			frappe.set_route(target);
		} catch (e) {
			/* never break the desk */
		}
	}

	// app_ready fires after boot + router init; the timeout is a safety net in
	// case the event has already fired by the time this script runs.
	$(document).on("app_ready", maybe_redirect);
	setTimeout(maybe_redirect, 2000);
})();
