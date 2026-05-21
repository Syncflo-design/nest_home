// nest_home — role-based, branded landing page (push, not pull).
// Built as a desk Page (not listview hooks) per CoWork_Helper gotchas
// 2026-05-11. Mounts inside page.body (jQuery in v16) per 2026-05-10.
// HTML is assembled as string arrays joined with "\n" (page-bundle rule).
//
// v0.0.3 layout: buttons sit in a narrow left column (2 wide); the attention
// lists spread across the rest of the screen as columns. Each list row shows
// only the company/lead name + due date — the rest is one click away.

frappe.pages['nest-home'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Nest Home',
		single_column: true
	});

	var BUILD_MARKER = 'v0.0.3-2026-05-21-horizontal-layout';
	console.log('Nest Home loaded:', BUILD_MARKER);

	// Load page styles from the separate CSS file (keeps this JS well under the
	// Cowork ~20KB Write/Edit truncation cap; CSS split from line one).
	if (!document.getElementById('nest-home-stylesheet')) {
		var link = document.createElement('link');
		link.id = 'nest-home-stylesheet';
		link.rel = 'stylesheet';
		link.href = '/assets/nest_home/css/nest_home.css';
		document.head.appendChild(link);
	}

	wrapper.nestHome = window.nestHome = new NestHome(page, BUILD_MARKER);
};

frappe.pages['nest-home'].on_page_show = function(wrapper) {
	if (wrapper.nestHome) wrapper.nestHome.refresh();
};

// ---------------------------------------------------------------------------

var NH_LIST_META = {
	A: { title: 'My Activities',      sub: 'Do these',     dot: 'nh-dot-A',
	     empty_title: "You're all clear", empty_msg: 'No activities need you right now.' },
	B: { title: 'Awaiting My Action', sub: 'Your call',    dot: 'nh-dot-B',
	     empty_title: 'Nothing awaiting you', empty_msg: 'No drafts are waiting on your decision.' },
	C: { title: 'Waiting On Others',  sub: 'Chase these',  dot: 'nh-dot-C',
	     empty_title: 'Nothing outstanding', empty_msg: "No one owes you anything right now." }
};

// Due-date rendering for a condensed row. Returns formatted text + overdue flag.
function nh_due(it) {
	if (!it || !it.date) return { text: '', over: false };
	var txt = it.date;
	try { txt = frappe.datetime.str_to_user(it.date); } catch (e) {}
	var over = false;
	try {
		var d = new Date(it.date);
		var today = new Date(); today.setHours(0, 0, 0, 0);
		over = d && !isNaN(d.getTime()) && d < today;
	} catch (e) {}
	return { text: txt, over: over };
}

class NestHome {

	constructor(page, build) {
		this.page = page;
		this.build = build;
		this.allowed = ['A'];           // refined once context loads
		this.poll_handle = null;

		// v16 modern desk: page.body is a jQuery object (NOT a DOM element).
		// Create our own container — never $(wrapper).find('.x'). See
		// gotchas/2026-05-10-frappe-v16-page-api-drift.md (Variant 2).
		this.$main = $('<div class="nest-home-root"></div>').appendTo(page.body);

		this.setup_page_actions();
		this.render_shell();
		this.bind_events();
		this.start_clock();
		this.init();
	}

	setup_page_actions() {
		var me = this;
		this.page.set_secondary_action('Refresh', function() { me.refresh(); }, 'refresh');
	}

	render_shell() {
		var shell = [
			'<div class="nh-app">',
			'  <div class="nh-header">',
			'    <div class="nh-header-left">',
			'      <span id="nh-logo-slot"></span>',
			'      <div>',
			'        <div class="nh-title" id="nh-title">Nest Home</div>',
			'        <div class="nh-greeting" id="nh-greeting"></div>',
			'      </div>',
			'    </div>',
			'    <div class="nh-header-right">',
			'      <div class="nh-clock" id="nh-clock"></div>',
			'      <div class="nh-date" id="nh-date"></div>',
			'    </div>',
			'  </div>',
			'  <div class="nh-body">',
			'    <div class="nh-left" id="nh-left" style="display:none;">',
			'      <div class="nh-section-label">Quick launch</div>',
			'      <div class="nh-tiles" id="nh-tiles"></div>',
			'    </div>',
			'    <div class="nh-right">',
			'      <div class="nh-section-label">Needs your attention</div>',
			'      <div class="nh-lists" id="nh-lists"></div>',
			'    </div>',
			'  </div>',
			'</div>'
		].join('\n');
		this.$main.html(shell);

		// Co-branding footer: subtle 'Powered by NestERP'. Hidden until the
		// landing context confirms the credit should show (white-label toggle).
		$('.nh-app', this.$main).append([
			'<div class="nh-footer" id="nh-footer" style="display:none;">',
			'  <span class="nh-powered">Powered by</span>',
			'  <img class="nh-nest-logo" src="/assets/nest_home/images/nesterp_logo.svg" alt="NestERP">',
			'  <span class="nh-nest-name">NestERP</span>',
			'</div>'
		].join('\n'));
	}

	bind_events() {
		var me = this;
		// Attention item → open its source via the normalised deep_link array.
		this.$main.on('click', '.nh-item', function() {
			var route = $(this).data('route');
			if (route) {
				try { route = JSON.parse(decodeURIComponent(route)); } catch (e) {}
				if (Array.isArray(route)) frappe.set_route.apply(frappe, route);
			}
		});
		// Quick-launch tile → navigate to its route.
		this.$main.on('click', '.nh-tile', function() {
			me.open_route($(this).data('route'));
		});
	}

	open_route(route) {
		if (!route) return;
		if (/^https?:/i.test(route)) { window.open(route, '_blank'); return; }
		var r = String(route).replace(/^\/app\//, '').replace(/^\//, '');
		frappe.set_route(r ? r.split('/') : ['']);
	}

	// ---- lifecycle -------------------------------------------------------

	init() {
		var me = this;
		this.load_context().then(function() {
			me.build_list_sections();
			me.load_visible();      // List A paints first; B/C fill behind it.
			me.start_poll();
		});
	}

	// Load whatever lists this user is allowed to see, List A first so login
	// feels instant, then the rest behind it.
	load_visible() {
		if (!this.allowed || !this.allowed.length) return;
		if (this.allowed.indexOf('A') >= 0) this.load_category('A');
		var rest = this.allowed.filter(function(c) { return c !== 'A'; });
		if (rest.length) this.load_categories(rest);
	}

	load_context() {
		var me = this;
		return frappe.call({ method: 'nest_home.api.get_landing_context' })
			.then(function(r) {
				var ctx = (r && r.message) || {};
				me.allowed = (ctx.allowed_lists && ctx.allowed_lists.length) ? ctx.allowed_lists : ['A'];
				me.render_header(ctx);
				me.render_tiles(ctx.tiles || []);
			})
			.catch(function() { me.allowed = ['A']; });
	}

	render_header(ctx) {
		var esc = frappe.utils.escape_html;
		$('#nh-title').text(ctx.app_title || 'Nest Home');
		if (ctx.show_nest_credit !== false) $('#nh-footer').show();
		var greet = ctx.greeting || ('Welcome back, ' + (ctx.user_fullname || '') + '.');
		$('#nh-greeting').text(greet);

		var $slot = $('#nh-logo-slot').empty();
		if (ctx.logo_url) {
			$slot.append($('<img class="nh-logo">').attr('src', ctx.logo_url).attr('alt', 'logo'));
		} else {
			var initial = (ctx.user_fullname || 'N').trim().charAt(0).toUpperCase();
			$slot.append('<span class="nh-logo-fallback">' + esc(initial) + '</span>');
		}
	}

	render_tiles(tiles) {
		// No buttons → hide the left column entirely so the lists take the full
		// width of the screen.
		if (!tiles || !tiles.length) { $('#nh-left').hide(); return; }
		var esc = frappe.utils.escape_html;
		var html = tiles.map(function(t) {
			var accent = t.color ? (' style="--nh-tile-accent:' + esc(t.color) + ';"') : '';
			var icon = nh_tile_icon(t);
			var icon_cls = t.icon_image ? 'nh-tile-icon nh-tile-icon-img' : 'nh-tile-icon';
			return [
				'<div class="nh-tile"' + accent + ' data-route="' + esc(t.route || '') + '">',
				'  <div class="' + icon_cls + '">' + icon + '</div>',
				'  <div class="nh-tile-label">' + esc(t.label || '') + '</div>',
				'</div>'
			].join('\n');
		}).join('\n');
		$('#nh-tiles').html(html);
		$('#nh-left').show();

		// An uploaded image (icon_image) wins; then a URL/path in `icon`; then a
		// Font Awesome / Octicon class; otherwise treat `icon` as emoji / text.
		function nh_tile_icon(t) {
			if (t.icon_image) return '<img src="' + esc(t.icon_image) + '" alt="">';
			var ic = t.icon;
			if (!ic) return '<i class="fa fa-rocket"></i>';
			if (/^https?:|^\//.test(ic)) return '<img src="' + esc(ic) + '" alt="">';
			if (/octicon|^fa /.test(ic)) return '<i class="' + esc(ic) + '"></i>';
			return esc(ic);
		}
	}

	build_list_sections() {
		var html = this.allowed.map(function(cat) {
			var m = NH_LIST_META[cat];
			return [
				'<section class="nh-list" id="nh-list-' + cat + '">',
				'  <div class="nh-list-head">',
				'    <div>',
				'      <div class="nh-list-title"><span class="nh-dot ' + m.dot + '"></span>' + m.title + '</div>',
				'      <div class="nh-list-sub">' + m.sub + '</div>',
				'    </div>',
				'    <span class="nh-count nh-zero" id="nh-count-' + cat + '">0</span>',
				'  </div>',
				'  <div class="nh-list-body" id="nh-body-' + cat + '">',
				'    <div class="nh-loading">Loading…</div>',
				'  </div>',
				'</section>'
			].join('\n');
		}).join('\n');
		$('#nh-lists').html(html);
	}

	// ---- data ------------------------------------------------------------

	load_category(cat) { return this.load_categories([cat]); }

	load_categories(cats) {
		var me = this;
		return frappe.call({
			method: 'nest_home.api.get_attention',
			args: { categories: JSON.stringify(cats) }
		}).then(function(r) {
			var data = (r && r.message) || {};
			cats.forEach(function(cat) { me.render_list(cat, data[cat] || []); });
		}).catch(function() {
			cats.forEach(function(cat) {
				$('#nh-body-' + cat).html('<div class="nh-error">Could not load this list.</div>');
			});
		});
	}

	render_list(cat, items) {
		var $body = $('#nh-body-' + cat);
		var $count = $('#nh-count-' + cat);
		$count.text(items.length).toggleClass('nh-zero', items.length === 0);

		if (!items.length) { $body.html(this.empty_state(cat)); return; }

		var me = this;
		var rows = items.map(function(it) { return me.item_html(it); }).join('\n');
		$body.html(rows);
	}

	// Condensed row: company/lead name on the left, due date on the right.
	// Everything else (priority, amount, description, status) is one click away.
	item_html(it) {
		var esc = frappe.utils.escape_html;
		var route = encodeURIComponent(JSON.stringify(it.deep_link || []));
		var main = it.owner_or_party || it.title || '(untitled)';
		var due = nh_due(it);
		var due_html = due.text
			? '<span class="nh-due' + (due.over ? ' nh-due-over' : '') + '">' + esc(due.text) + '</span>'
			: '<span class="nh-due nh-due-none">No date</span>';

		return [
			'<div class="nh-item" data-route="' + route + '">',
			'  <div class="nh-item-main"><div class="nh-item-title">' + esc(main) + '</div></div>',
			'  <div class="nh-item-right">' + due_html + '</div>',
			'</div>'
		].join('\n');
	}

	empty_state(cat) {
		var m = NH_LIST_META[cat];
		return [
			'<div class="nh-empty">',
			'  <div class="nh-empty-check"><i class="fa fa-check"></i></div>',
			'  <div class="nh-empty-title">' + m.empty_title + '</div>',
			'  <div class="nh-empty-msg">' + m.empty_msg + '</div>',
			'</div>'
		].join('\n');
	}

	// ---- refresh + quiet poll -------------------------------------------

	refresh() {
		this.load_visible();
	}

	start_poll() {
		var me = this;
		if (this.poll_handle) return;
		// Quiet poll every 2 minutes, only when the tab is visible. v1 freshness
		// is load + manual refresh + this gentle poll; live socket push is phase 2.
		this.poll_handle = setInterval(function() {
			if (document.visibilityState === 'visible') me.refresh();
		}, 120000);
	}

	start_clock() {
		var $c = function() { return $('#nh-clock'); };
		var $d = function() { return $('#nh-date'); };
		function tick() {
			var now = new Date();
			var hh = String(now.getHours()).padStart(2, '0');
			var mm = String(now.getMinutes()).padStart(2, '0');
			$c().text(hh + ':' + mm);
			$d().text(now.toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' }));
		}
		tick();
		setInterval(tick, 30000);
	}
}
