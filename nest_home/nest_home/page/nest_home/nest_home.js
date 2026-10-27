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

	var BUILD_MARKER = 'v0.0.30-2026-10-27-count-badge';
	console.log('Nest Home loaded:', BUILD_MARKER);

	// Load page styles from the separate CSS file (keeps this JS well under the
	// Cowork ~20KB Write/Edit truncation cap; CSS split from line one).
	// Phosphor icon font (regular + duotone, vendored) is loaded alongside it.
	[
		['nest-home-stylesheet', '/assets/nest_home/css/nest_home.css'],
		['nest-home-phosphor', '/assets/nest_home/vendor/phosphor/regular/style.css'],
		['nest-home-phosphor-duotone', '/assets/nest_home/vendor/phosphor/duotone/style.css']
	].forEach(function(css) {
		if (document.getElementById(css[0])) return;
		var link = document.createElement('link');
		link.id = css[0];
		link.rel = 'stylesheet';
		link.href = css[1];
		document.head.appendChild(link);
	});

	wrapper.nestHome = window.nestHome = new NestHome(page, BUILD_MARKER);
};

frappe.pages['nest-home'].on_page_show = function(wrapper) {
	if (wrapper.nestHome) {
		wrapper.nestHome.refresh();
		wrapper.nestHome.collapse_sidebar();
	}
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

// Comparator for two display strings; blanks sort last, case-insensitive.
function nh_cmp(x, y) {
	x = (x || '').toLowerCase(); y = (y || '').toLowerCase();
	if (!x && !y) return 0;
	if (!x) return 1;
	if (!y) return -1;
	return x < y ? -1 : (x > y ? 1 : 0);
}

// Returns a sort comparator for the given key (date|contact|company).
function nh_sorter(key) {
	if (key === 'contact') {
		return function(a, b) { return nh_cmp((a.meta || {}).contact, (b.meta || {}).contact); };
	}
	if (key === 'company') {
		return function(a, b) { return nh_cmp((a.meta || {}).company, (b.meta || {}).company); };
	}
	// default: due date ascending, undated rows last.
	return function(a, b) {
		var ad = a.date || '', bd = b.date || '';
		if (!ad && !bd) return 0;
		if (!ad) return 1;
		if (!bd) return -1;
		return ad < bd ? -1 : (ad > bd ? 1 : 0);
	};
}

// Font Awesome 4 names that tiles were set up with, and the Phosphor glyph for each.
function nh_fa_to_ph(name) {
	var map = {
		'credit-card': 'credit-card', 'calculator': 'calculator', 'truck': 'truck',
		'cubes': 'cubes', 'cube': 'cube', 'users': 'users', 'user': 'user', 'user-plus': 'user-plus',
		'file-text-o': 'file-text', 'file-text': 'file-text', 'files-o': 'files', 'book': 'book',
		'upload': 'upload-simple', 'download': 'download-simple', 'plus-circle': 'plus-circle',
		'bar-chart': 'chart-bar', 'line-chart': 'chart-line', 'pie-chart': 'chart-pie',
		'shopping-cart': 'shopping-cart', 'shopping-bag': 'shopping-bag', 'shopping-basket': 'basket',
		'address-book': 'address-book', 'tags': 'tag', 'tag': 'tag', 'paint-brush': 'paint-brush',
		'cog': 'gear', 'cogs': 'gears', 'life-ring': 'lifebuoy', 'globe': 'globe', 'industry': 'factory',
		'tasks': 'list-checks', 'check-square-o': 'check-square', 'check': 'check',
		'share-square-o': 'share', 'share': 'share', 'home': 'house', 'refresh': 'arrow-clockwise',
		'search': 'magnifying-glass', 'calendar': 'calendar', 'envelope': 'envelope', 'phone': 'phone',
		'map-marker': 'map-pin', 'list': 'list', 'table': 'table', 'archive': 'archive', 'print': 'printer',
		'money': 'money', 'dollar': 'currency-dollar', 'exchange': 'arrows-left-right', 'clock-o': 'clock',
		'question-circle': 'question', 'info-circle': 'info', 'wrench': 'wrench', 'flask': 'flask'
	};
	return map[name] || 'squares-four';
}

class NestHome {

	constructor(page, build) {
		this.page = page;
		this.build = build;
		this.allowed = ['A'];           // refined once context loads
		this.poll_handle = null;
		this.items = {};        // last-loaded items per category (client filter/sort)
		this.filter_text = {};  // active search text per category
		this.sort_key = {};     // active sort key per category

		// v16 modern desk: page.body is a jQuery object (NOT a DOM element).
		// Create our own container — never $(wrapper).find('.x'). See
		// gotchas/2026-05-10-frappe-v16-page-api-drift.md (Variant 2).
		this.$main = $('<div class="nest-home-root"></div>').appendTo(page.body);

		this.setup_page_actions();
		this.render_shell();
		this.bind_events();
		this.start_clock();
		this.init();
		this.collapse_sidebar();
	}

	// Auto-hide the desk sidebar on arrival. Clicks Frappe's own toggle (so the
	// user can click it again to bring the sidebar back) and only ever collapses,
	// never force-expands. Runs every time the page is shown (on_page_show +
	// initial make). Selector list is defensive across v15/v16 desk markup.
	collapse_sidebar() {
		var tries = 0;
		var iv = setInterval(function() {
			tries++;
			var $toggle = $('.sidebar-toggle-btn, .collapse-sidebar, .sidebar-toggle')
				.filter(':visible').first();
			if ($toggle.length) {
				var $sb = $('.body-sidebar-container, .desk-sidebar').first();
				var collapsed = $('body').is('.sidebar-collapsed')
					|| $sb.is('.sidebar-collapsed, .collapsed');
				if (!collapsed) $toggle.get(0).click();
				clearInterval(iv);
			} else if (tries > 15) {
				clearInterval(iv);
			}
		}, 120);
	}

	setup_page_actions() {
		// Single header bar: hide the default desk page-head. Home + Refresh now
		// live in the branded header (see render_shell / bind_events).
		var $head = this.page.head ? $(this.page.head) : $(this.page.wrapper).find('.page-head');
		if ($head && $head.length) $head.hide();
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
			'      <div class="nh-clockwrap">',
			'        <div class="nh-clock" id="nh-clock"></div>',
			'        <div class="nh-date" id="nh-date"></div>',
			'      </div>',
			'      <img class="nh-header-nest" id="nh-header-nest" src="/assets/nest_home/images/nesterp_logo.svg" alt="NestERP" title="NestERP" style="display:none;">',
			'      <div class="nh-header-actions">',
			'        <button class="nh-hbtn" id="nh-home" title="Home" aria-label="Home"><i class="ph ph-house"></i></button>',
			'        <button class="nh-hbtn" id="nh-refresh" title="Refresh" aria-label="Refresh"><i class="ph ph-arrow-clockwise"></i></button>',
			'      </div>',
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
			'  <span class="nh-foot-sep" id="nh-foot-sep" style="display:none;">&middot;</span>',
			'  <a class="nh-support" id="nh-support" style="display:none;"></a>',
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
			me.open_route($(this).data('route'), $(this).data('newtab'));
		});
		// Header controls.
		this.$main.on('click', '#nh-refresh', function() { me.refresh(); });
		this.$main.on('click', '#nh-home', function() { frappe.set_route('nest-home'); });

		// List filter + sort (currently My Activities only) — client-side.
		this.$main.on('input', '.nh-filter', function() {
			var cat = (this.id || '').replace('nh-filter-', '');
			me.filter_text[cat] = this.value || '';
			me.apply_view(cat);
		});
		this.$main.on('change', '.nh-sort', function() {
			var cat = (this.id || '').replace('nh-sort-', '');
			me.sort_key[cat] = this.value || 'date';
			me.apply_view(cat);
		});
	}

	open_route(route, new_tab) {
		if (!route) return;
		route = String(route);
		// Website/portal routes are absolute paths outside the desk (not under /desk or
		// the old /app); open them as real page loads instead of the desk router.
		if (route.charAt(0) === '/' && !/^\/(desk|app)(\/|$|\?|#)/.test(route)) {
			if (new_tab) window.open(route, '_blank');
			else window.location.href = route;
			return;
		}
		var r = route.replace(/^\/(desk|app)\//, '').replace(/^\//, '');
		if (new_tab || /^https?:/i.test(route)) {
			// Frappe 16 serves the desk at /desk (the old /app answers Page not found).
			var url = /^https?:/i.test(route) ? route : window.location.origin + '/desk/' + r;
			window.open(url, '_blank');
			return;
		}
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
				// A layout may switch every list off; only a missing answer falls back to List A.
				me.allowed = Array.isArray(ctx.allowed_lists) ? ctx.allowed_lists : ['A'];
				me.render_header(ctx);
				me.render_tiles(ctx.tiles || []);
				if (!me.allowed.length) {
					$('.nh-right', me.$main).hide();
					$('#nh-left').addClass('nh-full');
				}
			})
			.catch(function() { me.allowed = ['A']; });
	}

	render_header(ctx) {
		var esc = frappe.utils.escape_html;
		$('#nh-title').text(ctx.app_title || 'Nest Home');
		if (ctx.show_nest_credit !== false) {
			$('#nh-footer').show();
			$('#nh-header-nest').show();
		}
		if (ctx.support_link) {
			var sl = String(ctx.support_link).trim();
			var href = (/@/.test(sl) && !/:\/\//.test(sl)) ? ('mailto:' + sl) : sl;
			$('#nh-support').attr('href', href).text('Contact support');
			$('#nh-foot-sep').show();
			$('#nh-support').show();
		}
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
			var help_slug = esc(t.label || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/-+$/, '');
			return [
				'<div class="nh-tile"' + accent + ' data-route="' + esc(t.route || '') + '"' + (t.open_in_new_tab ? ' data-newtab="1"' : '') + (t.count_method ? ' data-count="' + esc(t.count_method) + '"' : '') + ' data-help="' + help_slug + '">',
				'  <div class="' + icon_cls + '">' + icon + '</div>',
				'  <div class="nh-tile-label">' + esc(t.label || '') + '</div>',
				'</div>'
			].join('\n');
		}).join('\n');
		$('#nh-tiles').html(html);
		$('#nh-left').show();
		this.load_counts();
		// If nest_help app is installed, auto-discover help badges for tiles.
		if (window.nestHelp) window.nestHelp.discover($('#nh-tiles'));

		// An uploaded image (icon_image) wins; then a URL/path in `icon`; then a
		// Phosphor class; a Font Awesome name is drawn with the matching Phosphor
		// glyph (Frappe 16.51 no longer ships Font Awesome on the desk); an Octicon
		// class is passed through; otherwise `icon` is treated as text.
		function nh_tile_icon(t) {
			if (t.icon_image) return '<img src="' + esc(t.icon_image) + '" alt="">';
			var ic = t.icon;
			if (!ic) return '<i class="ph-duotone ph-rocket-launch"></i>';
			if (/^https?:|^\//.test(ic)) return '<img src="' + esc(ic) + '" alt="">';
			if (/^ph(-[a-z]+)? ph-/.test(ic)) return '<i class="' + esc(ic) + '"></i>';
			var fa = ic.match(/^fa fa-([a-z0-9-]+)/);
			if (fa) return '<i class="ph-duotone ph-' + nh_fa_to_ph(fa[1]) + '"></i>';
			if (/octicon/.test(ic)) return '<i class="' + esc(ic) + '"></i>';
			return esc(ic);
		}
	}

	build_list_sections() {
		var html = this.allowed.map(function(cat) {
			var m = NH_LIST_META[cat];
			// My Activities (A) gets a filter + sort toolbar in its header.
			var tools = (cat === 'A') ? [
				'  <div class="nh-list-tools">',
				'    <input type="text" class="nh-filter" id="nh-filter-' + cat + '" placeholder="Filter by contact or company…" autocomplete="off">',
				'    <select class="nh-sort" id="nh-sort-' + cat + '" title="Sort">',
				'      <option value="date">Due date</option>',
				'      <option value="contact">Contact A-Z</option>',
				'      <option value="company">Company A-Z</option>',
				'    </select>',
				'  </div>'
			].join('\n') : '';
			return [
				'<section class="nh-list" id="nh-list-' + cat + '">',
				'  <div class="nh-list-head">',
				'    <div>',
				'      <div class="nh-list-title"><span class="nh-dot ' + m.dot + '"></span>' + m.title + '</div>',
				'      <div class="nh-list-sub">' + m.sub + '</div>',
				'    </div>',
				'    <span class="nh-count nh-zero" id="nh-count-' + cat + '">0</span>',
				tools,
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
			args: { categories: JSON.stringify(cats), limit_per: 200 }
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
		this.items[cat] = items || [];
		this.apply_view(cat);
	}

	// Render a category's stored items through its active filter + sort.
	// Filter matches contact OR company (case-insensitive substring); sort key
	// is date|contact|company. Cheap enough to re-run on every keystroke / poll.
	apply_view(cat) {
		var $body = $('#nh-body-' + cat);
		var $count = $('#nh-count-' + cat);
		var all = this.items[cat] || [];
		var q = (this.filter_text[cat] || '').trim().toLowerCase();

		var items = all;
		if (q) {
			items = all.filter(function(it) {
				var m = it.meta || {};
				var c = (m.contact || '').toLowerCase();
				var co = (m.company || '').toLowerCase();
				return c.indexOf(q) >= 0 || co.indexOf(q) >= 0;
			});
		}
		items = items.slice().sort(nh_sorter(this.sort_key[cat] || 'date'));

		$count.text(items.length).toggleClass('nh-zero', items.length === 0);

		if (!items.length) {
			if (q && all.length) {
				$body.html('<div class="nh-empty"><div class="nh-empty-title">No matches</div>'
					+ '<div class="nh-empty-msg">Nothing matches “'
					+ frappe.utils.escape_html(q) + '”.</div></div>');
			} else {
				$body.html(this.empty_state(cat));
			}
			return;
		}

		var me = this;
		$body.html(items.map(function(it) { return me.item_html(it); }).join('\n'));
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
			'  <div class="nh-empty-check"><i class="ph ph-check"></i></div>',
			'  <div class="nh-empty-title">' + m.empty_title + '</div>',
			'  <div class="nh-empty-msg">' + m.empty_msg + '</div>',
			'</div>'
		].join('\n');
	}

	// ---- refresh + quiet poll -------------------------------------------

	refresh() {
		this.load_visible();
		this.load_counts();
	}

	// A tile with a Count Method shows that number as a red badge on its icon while it
	// is above 0 (e.g. stock requests waiting to be issued). An existing badge is updated
	// in place so the poll does not replay its entrance.
	load_counts() {
		$('#nh-tiles .nh-tile[data-count]').each(function() {
			var $tile = $(this);
			frappe.call({ method: $tile.attr('data-count') }).then(function(r) {
				var n = cint(r && r.message);
				var $icon = $tile.find('.nh-tile-icon');
				var $badge = $icon.find('.nh-tile-count');
				if (n <= 0) { $badge.remove(); return; }
				if (!$badge.length) $badge = $('<span class="nh-tile-count"></span>').appendTo($icon);
				var label = __('{0} waiting', [n]);
				$badge.text(n > 99 ? '99+' : String(n)).attr({ title: label, 'aria-label': label, role: 'status' });
			});
		});
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
