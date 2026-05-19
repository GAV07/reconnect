/* search.js — Semantic people search (main app experience) */

const SEARCH_FUNCTION_URL = window.RECONNECT_CONFIG?.supabaseUrl
  ? window.RECONNECT_CONFIG.supabaseUrl + '/functions/v1/search'
  : '';

let _searchDebounce = null;
let _searchResults = [];
let _searchQuery = '';
let _searchLoading = false;
let _searchError = '';
let _totalContacts = null;

async function renderSearch(container) {
  if (!db) {
    container.innerHTML = '<div class="empty-state"><div class="icon">&#9888;</div><p>Supabase not configured.</p></div>';
    return;
  }

  // Get total count on first load
  if (_totalContacts === null) {
    var countResult = await db
      .from('connections')
      .select('id', { count: 'exact', head: true })
      .or('user_priority.neq.never,user_priority.is.null');
    _totalContacts = countResult.count || 0;
  }

  var headerSub = document.querySelector('.app-header .subtitle');
  if (headerSub) {
    headerSub.textContent = _totalContacts + ' people in your network';
  }

  renderSearchPage(container);
}

function renderSearchPage(container) {
  var html = '';

  // Search input — big, prominent, centered
  html += '<div class="search-hero">';
  html += '<div class="search-hero-input-wrap">';
  html += '<svg class="search-hero-icon" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">';
  html += '<circle cx="8.5" cy="8.5" r="5.5"/>';
  html += '<line x1="13" y1="13" x2="18" y2="18"/>';
  html += '</svg>';
  html += '<input type="search" class="search-hero-input" id="semantic-search-input"';
  html += ' placeholder="Describe who you\'re looking for..."';
  html += ' value="' + escapeHtml(_searchQuery) + '"';
  html += ' oninput="onSemanticSearchInput(this.value)"';
  html += ' onkeydown="if(event.key===\'Enter\')runSemanticSearch()"';
  html += ' autofocus';
  html += '/>';
  if (_searchQuery) {
    html += '<button class="search-clear-btn" onclick="clearSemanticSearch()" aria-label="Clear search">&times;</button>';
  }
  html += '</div>';
  html += '<div class="search-hint">Try: "designer at a startup in SF" or "someone in climate tech"</div>';
  html += '</div>';

  // Loading state
  if (_searchLoading) {
    html += '<div class="loading"><div class="spinner"></div> Searching...</div>';
    container.innerHTML = html;
    return;
  }

  // Error state
  if (_searchError) {
    html += '<div class="search-error">' + escapeHtml(_searchError) + '</div>';
  }

  // Results
  if (_searchResults.length > 0) {
    html += '<div class="search-results-count">' + _searchResults.length + ' match' + (_searchResults.length !== 1 ? 'es' : '') + '</div>';
    html += _searchResults.map(renderSearchResult).join('');
  } else if (_searchQuery && !_searchLoading) {
    html += '<div class="empty-state"><div class="icon">&#128269;</div><p>No matches for "' + escapeHtml(_searchQuery) + '"</p><p class="search-empty-hint">Try broader terms or different phrasing</p></div>';
  } else if (!_searchQuery) {
    // Show recent / suggested when no search active
    html += renderSearchSuggestions();
  }

  container.innerHTML = html;

  // Restore focus to input
  var input = document.getElementById('semantic-search-input');
  if (input) {
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  }
}

function renderSearchResult(result) {
  var name = escapeHtml(result.name || 'Unknown');
  var role = escapeHtml(result.current_role || '');
  var company = escapeHtml(result.current_company || '');
  var roleLine = company ? role + ' @ ' + company : role;
  var industry = escapeHtml(result.enriched_industry || '');
  var city = escapeHtml(result.enriched_city || '');
  var school = escapeHtml(result.enriched_school || '');
  var similarity = result.similarity ? Math.round(result.similarity * 100) : 0;

  var chips = '';
  if (industry) chips += '<span class="industry-chip">' + industry + '</span>';
  if (city) chips += '<span class="search-result-city">' + city + '</span>';
  if (school) chips += '<span class="search-result-school">' + school + '</span>';

  return '<div class="search-result-card" onclick="navigate(\'#/contact/' + result.id + '\')">' +
    '<div class="search-result-header">' +
      '<div>' +
        '<div class="search-result-name">' + name + '</div>' +
        (roleLine ? '<div class="search-result-role">' + roleLine + '</div>' : '') +
      '</div>' +
      '<div class="search-match-badge" title="' + similarity + '% match">' + similarity + '%</div>' +
    '</div>' +
    (result.enriched_headline ? '<div class="search-result-headline">' + escapeHtml(result.enriched_headline) + '</div>' : '') +
    (chips ? '<div class="search-result-meta">' + chips + '</div>' : '') +
  '</div>';
}

function renderSearchSuggestions() {
  var suggestions = [
    'product manager at a startup',
    'someone in healthcare or biotech',
    'designer who posts about AI',
    'engineer at Google or Meta',
    'consultant in sustainability',
    'founder in fintech',
  ];

  var html = '<div class="search-suggestions">';
  html += '<div class="search-suggestions-title">Try searching for</div>';
  html += '<div class="search-suggestion-chips">';
  suggestions.forEach(function(s) {
    html += '<button class="search-suggestion-chip" onclick="runSuggestion(\'' + escapeHtml(s) + '\')">' + escapeHtml(s) + '</button>';
  });
  html += '</div>';
  html += '</div>';
  return html;
}

function onSemanticSearchInput(value) {
  _searchQuery = value;
  clearTimeout(_searchDebounce);

  if (!value.trim()) {
    _searchResults = [];
    _searchError = '';
    var content = document.getElementById('app-content');
    if (content) renderSearchPage(content);
    return;
  }

  // Auto-search after 600ms of inactivity (longer than keyword search since it calls an API)
  _searchDebounce = setTimeout(function() {
    runSemanticSearch();
  }, 600);
}

async function runSemanticSearch() {
  var query = _searchQuery.trim();
  if (!query) return;

  _searchLoading = true;
  _searchError = '';
  var content = document.getElementById('app-content');
  if (content) renderSearchPage(content);

  try {
    var response = await fetch(SEARCH_FUNCTION_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + window.RECONNECT_CONFIG.supabaseAnonKey,
      },
      body: JSON.stringify({ query: query, limit: 30 }),
    });

    if (!response.ok) {
      var errData = await response.json().catch(function() { return {}; });
      throw new Error(errData.error || 'Search failed');
    }

    var data = await response.json();
    _searchResults = data.results || [];
    _searchLoading = false;
  } catch (err) {
    console.error('Search error:', err);
    _searchError = err.message || 'Search failed. Please try again.';
    _searchResults = [];
    _searchLoading = false;
  }

  content = document.getElementById('app-content');
  if (content) renderSearchPage(content);
}

function runSuggestion(text) {
  _searchQuery = text;
  var input = document.getElementById('semantic-search-input');
  if (input) input.value = text;
  runSemanticSearch();
}

function clearSemanticSearch() {
  _searchQuery = '';
  _searchResults = [];
  _searchError = '';
  var content = document.getElementById('app-content');
  if (content) renderSearchPage(content);
}
