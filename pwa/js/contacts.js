/* contacts.js — Contacts browse page */

const BROWSE_SELECT = [
  'id', 'name', 'current_role', 'current_company',
  'enriched_industry', 'enriched_city', 'enriched_headline',
  'reconnect_score', 'latest_signal', 'user_priority'
].join(',');

const contactFilters = {
  searchQuery: '',
  industryFilter: null,
  cityFilter: null,
  offset: 0,
  totalCount: 0,
};

let _contactRows = [];
let _filterOptions = { industries: [], cities: [] };
let _searchDebounceTimer = null;
let _unfilteredTotal = 0;

/* --- Filter Options --- */

async function fetchFilterOptions() {
  const [indResult, cityResult] = await Promise.all([
    db.from('connections').select('enriched_industry').or('user_priority.neq.never,user_priority.is.null').not('enriched_industry', 'is', null),
    db.from('connections').select('enriched_city').or('user_priority.neq.never,user_priority.is.null').not('enriched_city', 'is', null),
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
      .or('user_priority.neq.never,user_priority.is.null');
    _unfilteredTotal = unfilteredResult.count || 0;
  }

  var query = db
    .from('connections')
    .select(BROWSE_SELECT, { count: 'exact' })
    .or('user_priority.neq.never,user_priority.is.null')
    .order('reconnect_score', { ascending: false })
    .range(contactFilters.offset, contactFilters.offset + 49);

  if (contactFilters.searchQuery) {
    query = query.textSearch('fts', contactFilters.searchQuery, {
      type: 'plain',
      config: 'english'
    });
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
    // If textSearch failed (fts column missing), retry with ilike fallback
    if (contactFilters.searchQuery && error.message && error.message.includes('fts')) {
      console.warn('textSearch failed, falling back to ilike:', error.message);
      var fallbackQuery = db
        .from('connections')
        .select(BROWSE_SELECT, { count: 'exact' })
        .or('user_priority.neq.never,user_priority.is.null')
        .order('reconnect_score', { ascending: false })
        .range(contactFilters.offset, contactFilters.offset + 49);
      var terms = contactFilters.searchQuery.trim().split(/\s+/);
      terms.forEach(function(term) {
        var p = '%' + term + '%';
        fallbackQuery = fallbackQuery.or(
          'name.ilike.' + p + ',' +
          'current_role.ilike.' + p + ',' +
          'current_company.ilike.' + p + ',' +
          'enriched_city.ilike.' + p + ',' +
          'enriched_school.ilike.' + p
        );
      });
      if (contactFilters.industryFilter) {
        fallbackQuery = fallbackQuery.eq('enriched_industry', contactFilters.industryFilter);
      }
      if (contactFilters.cityFilter) {
        fallbackQuery = fallbackQuery.eq('enriched_city', contactFilters.cityFilter);
      }
      var fallbackResult = await fallbackQuery;
      data = fallbackResult.data;
      count = fallbackResult.count;
      error = fallbackResult.error;
    }
    if (error) {
      console.error('Contacts fetch error:', error);
      container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Failed to load contacts. Check your connection and try again.</p></div>';
      return;
    }
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
    var hasActiveFilter = contactFilters.searchQuery || contactFilters.industryFilter || contactFilters.cityFilter;
    if (hasActiveFilter) {
      if (contactFilters.searchQuery) {
        listHtml = '<div class="empty-state"><div class="icon">&#128269;</div><p>No contacts match "' + escapeHtml(contactFilters.searchQuery) + '". Try different keywords or clear your search.</p></div>';
      } else {
        listHtml = '<div class="empty-state"><div class="icon">&#128269;</div><p>No contacts match these filters. Try adjusting or clearing your filters.</p></div>';
      }
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
  var hasActiveFilter = contactFilters.searchQuery || contactFilters.industryFilter || contactFilters.cityFilter;

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
      '<label style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:var(--text-secondary);font-weight:600;">SEARCH</label>' +
      '<div class="search-input-wrap">' +
        '<svg class="search-icon-svg" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">' +
          '<circle cx="8.5" cy="8.5" r="5.5"/>' +
          '<line x1="13" y1="13" x2="18" y2="18"/>' +
        '</svg>' +
        '<input type="search" class="filter-input search-input"' +
          ' placeholder="Search contacts..."' +
          ' value="' + escapeHtml(contactFilters.searchQuery) + '"' +
          ' oninput="onContactSearchInput(this.value)"' +
        '/>' +
      '</div>' +
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
  if (contactFilters.searchQuery) {
    return '<div class="contacts-count-banner">' + total + ' contacts match "' + escapeHtml(contactFilters.searchQuery) + '"</div>';
  }
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
  contactFilters.searchQuery = '';
  contactFilters.industryFilter = null;
  contactFilters.cityFilter = null;
  contactFilters.offset = 0;
  var content = document.getElementById('app-content');
  if (content) renderContacts(content);
}

/* --- Search Input with Debounce --- */

function onContactSearchInput(value) {
  clearTimeout(_searchDebounceTimer);
  if (!value || value.length < 2) {
    if (!value) {
      contactFilters.searchQuery = '';
      contactFilters.offset = 0;
      var content = document.getElementById('app-content');
      if (content) renderContacts(content);
    }
    return;
  }
  _searchDebounceTimer = setTimeout(function() {
    contactFilters.searchQuery = value;
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
    .or('user_priority.neq.never,user_priority.is.null')
    .order('reconnect_score', { ascending: false })
    .range(contactFilters.offset, contactFilters.offset + 49);

  if (contactFilters.searchQuery) {
    query = query.textSearch('fts', contactFilters.searchQuery, {
      type: 'plain',
      config: 'english'
    });
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
