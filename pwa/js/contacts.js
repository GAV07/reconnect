/* contacts.js — Contacts browse page */

const BROWSE_SELECT = [
  'id', 'name', 'current_role', 'current_company',
  'enriched_industry', 'enriched_city', 'enriched_headline',
  'reconnect_score', 'latest_signal', 'user_priority'
].join(',');

const contactFilters = {
  roleQuery: '',
  industryFilter: null,
  cityFilter: null,
  offset: 0,
  totalCount: 0,
};

let _contactRows = [];
let _filterOptions = { industries: [], cities: [] };
let _roleDebounceTimer = null;
let _unfilteredTotal = 0;

/* --- Filter Options --- */

async function fetchFilterOptions() {
  const [indResult, cityResult] = await Promise.all([
    db.from('connections').select('enriched_industry').neq('user_priority', 'never').not('enriched_industry', 'is', null),
    db.from('connections').select('enriched_city').neq('user_priority', 'never').not('enriched_city', 'is', null),
  ]);

  const industries = [...new Set(
    (indResult.data || []).map(function(r) { return r.enriched_industry; }).filter(Boolean)
  )].sort();

  const cities = [...new Set(
    (cityResult.data || []).map(function(r) { return r.enriched_city; }).filter(Boolean)
  )].sort();

  return { industries: industries, cities: cities };
}

/* --- Main Render Function --- */

async function renderContacts(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Supabase not configured. Set your project URL and anon key in index.html.</p></div>';
    return;
  }

  if (contactFilters.offset === 0) {
    container.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';
    _contactRows = [];

    if (_filterOptions.industries.length === 0) {
      _filterOptions = await fetchFilterOptions();
    }

    var unfilteredResult = await db
      .from('connections')
      .select('id', { count: 'exact', head: true })
      .neq('user_priority', 'never');
    _unfilteredTotal = unfilteredResult.count || 0;
  }

  var query = db
    .from('connections')
    .select(BROWSE_SELECT, { count: 'exact' })
    .neq('user_priority', 'never')
    .order('reconnect_score', { ascending: false })
    .range(contactFilters.offset, contactFilters.offset + 49);

  if (contactFilters.roleQuery) {
    query = query.ilike('enriched_headline', '%' + contactFilters.roleQuery + '%');
  }
  if (contactFilters.industryFilter) {
    query = query.eq('enriched_industry', contactFilters.industryFilter);
  }
  if (contactFilters.cityFilter) {
    query = query.eq('enriched_city', contactFilters.cityFilter);
  }

  var result = await query;
  var data = result.data;
  var count = result.count;
  var error = result.error;

  if (error) {
    console.error('Contacts fetch error:', error);
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Failed to load contacts. Check your connection and try again.</p></div>';
    return;
  }

  contactFilters.totalCount = count || 0;

  if (contactFilters.offset === 0) {
    _contactRows = data || [];
  } else {
    _contactRows = _contactRows.concat(data || []);
  }

  var headerSub = document.querySelector('.app-header .subtitle');
  if (headerSub) {
    headerSub.textContent = _unfilteredTotal + ' connections';
  }

  renderContactsPage(container);
}

/* --- Page HTML Assembly --- */

function renderContactsPage(container) {
  var filterBarHtml = buildFilterBarHtml();
  var countBanner = buildCountBanner(_contactRows.length, contactFilters.totalCount);

  var listHtml = '';
  if (_contactRows.length === 0 && contactFilters.totalCount === 0) {
    var hasActiveFilter = contactFilters.roleQuery || contactFilters.industryFilter || contactFilters.cityFilter;
    if (hasActiveFilter) {
      listHtml = '<div class="empty-state"><div class="icon">&#128269;</div><p>No contacts match these filters. Try adjusting or clearing your filters.</p></div>';
    } else {
      listHtml = '<div class="empty-state"><div class="icon">&#128101;</div><p>No contacts yet. Import your LinkedIn connections to get started.</p></div>';
    }
  } else {
    listHtml = _contactRows.map(renderContactRow).join('');
  }

  var loadMoreHtml = '';
  if (_contactRows.length < contactFilters.totalCount) {
    loadMoreHtml = '<div class="load-more-container"><button class="btn btn-outline" onclick="loadMoreContacts(this)">Load more contacts</button></div>';
  }

  container.innerHTML = filterBarHtml + countBanner + listHtml + loadMoreHtml;
}

/* --- Contact Row Card --- */

function renderContactRow(conn) {
  var name = escapeHtml(conn.name || 'Unknown');
  var role = escapeHtml(conn.current_role || '');
  var company = escapeHtml(conn.current_company || '');
  var roleLine = company ? role + ' @ ' + company : role;
  var score = Math.round(conn.reconnect_score || 0);
  var industry = escapeHtml(conn.enriched_industry || '');
  var city = escapeHtml(conn.enriched_city || '');
  var signal = conn.latest_signal;
  var signalInfo = signal && typeof SIGNAL_ACTIONS !== 'undefined' && SIGNAL_ACTIONS[signal] ? SIGNAL_ACTIONS[signal] : null;

  var industryChip = industry
    ? '<span class="industry-chip">' + industry + '</span>'
    : '';
  var citySpan = city
    ? '<span class="contact-row-city">' + city + '</span>'
    : '';
  var signalBadge = signalInfo
    ? '<span class="signal-badge" style="background:' + signalInfo.bg + ';color:' + signalInfo.color + ';">' + escapeHtml(signalInfo.label) + '</span>'
    : '';

  return '<div class="contact-row" onclick="navigate(\'#/contact/' + conn.id + '\')">' +
    '<div class="contact-row-header">' +
      '<div>' +
        '<div class="contact-row-name">' + name + '</div>' +
        (roleLine ? '<div class="contact-row-role">' + roleLine + '</div>' : '') +
      '</div>' +
      '<div class="score-badge">' + score + '</div>' +
    '</div>' +
    '<div class="contact-row-meta">' +
      industryChip + citySpan + signalBadge +
    '</div>' +
  '</div>';
}

/* --- Filter Bar HTML --- */

function buildFilterBarHtml() {
  var hasActiveFilter = contactFilters.roleQuery || contactFilters.industryFilter || contactFilters.cityFilter;

  var industryOptions = _filterOptions.industries.map(function(ind) {
    var selected = contactFilters.industryFilter === ind ? ' selected' : '';
    return '<option value="' + escapeHtml(ind) + '"' + selected + '>' + escapeHtml(ind) + '</option>';
  }).join('');

  var cityOptions = _filterOptions.cities.map(function(city) {
    var selected = contactFilters.cityFilter === city ? ' selected' : '';
    return '<option value="' + escapeHtml(city) + '"' + selected + '>' + escapeHtml(city) + '</option>';
  }).join('');

  var clearBtn = hasActiveFilter
    ? '<button class="btn btn-sm btn-outline" onclick="clearContactFilters()" style="align-self:flex-end;">Clear filters</button>'
    : '';

  return '<div class="contacts-filter-bar">' +
    '<div class="filter-group filter-group-full">' +
      '<label style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-secondary);font-weight:600;">ROLE / TITLE</label>' +
      '<input type="text" class="filter-input"' +
        ' placeholder="e.g. Product Manager"' +
        ' value="' + escapeHtml(contactFilters.roleQuery) + '"' +
        ' oninput="onContactRoleInput(this.value)"' +
        ' list="role-suggestions"' +
      '/>' +
      '<datalist id="role-suggestions"></datalist>' +
    '</div>' +
    '<div class="contacts-filter-row">' +
      '<div class="filter-group">' +
        '<label style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-secondary);font-weight:600;">INDUSTRY</label>' +
        '<select class="queue-filters select" onchange="setContactIndustryFilter(this.value)">' +
          '<option value="">All Industries</option>' +
          industryOptions +
        '</select>' +
      '</div>' +
      '<div class="filter-group">' +
        '<label style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-secondary);font-weight:600;">LOCATION</label>' +
        '<select class="queue-filters select" onchange="setContactCityFilter(this.value)">' +
          '<option value="">All Cities</option>' +
          cityOptions +
        '</select>' +
      '</div>' +
      clearBtn +
    '</div>' +
  '</div>';
}

/* --- Count Banner --- */

function buildCountBanner(showing, total) {
  if (total === 0) return '';
  return '<div class="contacts-count-banner">Showing ' + showing + ' of ' + total + ' contacts</div>';
}

/* --- Filter Action Functions --- */

function setContactIndustryFilter(value) {
  contactFilters.industryFilter = value || null;
  contactFilters.offset = 0;
  var content = document.getElementById('app-content');
  if (content) renderContacts(content);
}

function setContactCityFilter(value) {
  contactFilters.cityFilter = value || null;
  contactFilters.offset = 0;
  var content = document.getElementById('app-content');
  if (content) renderContacts(content);
}

function clearContactFilters() {
  contactFilters.roleQuery = '';
  contactFilters.industryFilter = null;
  contactFilters.cityFilter = null;
  contactFilters.offset = 0;
  var content = document.getElementById('app-content');
  if (content) renderContacts(content);
}

/* --- Role Autocomplete with Debounce --- */

function onContactRoleInput(value) {
  clearTimeout(_roleDebounceTimer);
  if (value.length < 2) {
    var dl = document.getElementById('role-suggestions');
    if (dl) dl.innerHTML = '';
    if (!value) {
      contactFilters.roleQuery = '';
      contactFilters.offset = 0;
      var content = document.getElementById('app-content');
      if (content) renderContacts(content);
    }
    return;
  }
  _roleDebounceTimer = setTimeout(async function() {
    if (db) {
      var result = await db
        .from('connections')
        .select('enriched_headline')
        .not('enriched_headline', 'is', null)
        .ilike('enriched_headline', '%' + value + '%')
        .limit(10);
      var suggestions = [...new Set((result.data || []).map(function(r) { return r.enriched_headline; }).filter(Boolean))];
      var dl = document.getElementById('role-suggestions');
      if (dl) {
        dl.innerHTML = suggestions.map(function(s) { return '<option value="' + escapeHtml(s) + '">'; }).join('');
      }
    }
    contactFilters.roleQuery = value;
    contactFilters.offset = 0;
    var content = document.getElementById('app-content');
    if (content) renderContacts(content);
  }, 300);
}

/* --- Load More --- */

async function loadMoreContacts(btn) {
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Loading...';
  }
  contactFilters.offset += 50;

  var query = db
    .from('connections')
    .select(BROWSE_SELECT)
    .neq('user_priority', 'never')
    .order('reconnect_score', { ascending: false })
    .range(contactFilters.offset, contactFilters.offset + 49);

  if (contactFilters.roleQuery) {
    query = query.ilike('enriched_headline', '%' + contactFilters.roleQuery + '%');
  }
  if (contactFilters.industryFilter) {
    query = query.eq('enriched_industry', contactFilters.industryFilter);
  }
  if (contactFilters.cityFilter) {
    query = query.eq('enriched_city', contactFilters.cityFilter);
  }

  var result = await query;
  if (result.data) {
    _contactRows = _contactRows.concat(result.data);
  }
  var content = document.getElementById('app-content');
  if (content) renderContactsPage(content);
}
