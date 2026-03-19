"""Phase 14 Search Bar validation tests.

Tests verify PWA static files and migration SQL contain expected patterns for
SEARCH-01 and SEARCH-02. Uses Python open() + string matching — same pattern
as tests/test_phase13_contacts.py.
"""

import os
import re

PWA_DIR = os.path.join(os.path.dirname(__file__), '..', 'pwa')
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', 'supabase', 'migrations')


def _read_pwa_file(relative_path):
    """Read a PWA file and return its contents."""
    path = os.path.join(PWA_DIR, relative_path)
    with open(path, 'r') as f:
        return f.read()


def _read_migration_file(filename):
    """Read a migration SQL file and return its contents."""
    path = os.path.join(MIGRATIONS_DIR, filename)
    with open(path, 'r') as f:
        return f.read()


# --- SEARCH-01: State migration (roleQuery → searchQuery) ---

def test_search_query_state():
    """contacts.js has searchQuery state variable and does NOT have roleQuery."""
    content = _read_pwa_file('js/contacts.js')
    assert 'searchQuery' in content, 'contacts.js must have searchQuery filter state'
    assert 'roleQuery' not in content, 'contacts.js must NOT have roleQuery (renamed to searchQuery in Phase 14)'


# --- SEARCH-01: FTS query path ---

def test_textsearch_call():
    """contacts.js queries fts column via PostgREST .textSearch() with type plain."""
    content = _read_pwa_file('js/contacts.js')
    assert '.textSearch(' in content, "contacts.js must call .textSearch() for FTS query"
    assert "'fts'" in content or '"fts"' in content, "contacts.js must reference 'fts' column in textSearch"
    assert 'plain' in content, "contacts.js must use type: 'plain' for textSearch (safe for raw user input)"


# --- SEARCH-01: ilike fallback ---

def test_ilike_fallback_pattern():
    """contacts.js has multi-column OR ilike fallback pattern for all searchable fields."""
    content = _read_pwa_file('js/contacts.js')
    assert 'name.ilike.' in content, "contacts.js must have name.ilike. in fallback .or() pattern"
    assert 'current_role.ilike.' in content, "contacts.js must have current_role.ilike. in fallback .or() pattern"
    assert 'current_company.ilike.' in content, "contacts.js must have current_company.ilike. in fallback .or() pattern"
    assert 'enriched_city.ilike.' in content, "contacts.js must have enriched_city.ilike. in fallback .or() pattern"
    assert 'enriched_school.ilike.' in content, "contacts.js must have enriched_school.ilike. in fallback .or() pattern"


# --- SEARCH-01: Migration SQL correctness ---

def test_migration_has_fts_column():
    """Migration SQL defines fts tsvector generated column on connections table."""
    content = _read_migration_file('20260318000000_fts_column.sql')
    assert 'fts tsvector' in content.lower(), "Migration must define 'fts tsvector' column"
    assert 'GENERATED ALWAYS AS' in content, "Migration must use GENERATED ALWAYS AS for auto-maintenance"
    assert 'to_tsvector' in content, "Migration must use to_tsvector() for the generated expression"


# --- SEARCH-01: GIN index ---

def test_migration_has_gin_index():
    """Migration SQL creates GIN index named idx_connections_fts on fts column."""
    content = _read_migration_file('20260318000000_fts_column.sql')
    assert 'USING GIN' in content.upper(), "Migration must create a GIN index on fts column"
    assert 'idx_connections_fts' in content, "Migration must name the index idx_connections_fts"


# --- SEARCH-02: Debounce ---

def test_search_debounce_pattern():
    """contacts.js has 300ms debounce via setTimeout for search input handler."""
    content = _read_pwa_file('js/contacts.js')
    assert '300' in content, "contacts.js must use 300ms debounce timer"
    assert 'setTimeout' in content, "contacts.js must use setTimeout for debounce"
    assert 'onContactSearchInput' in content, "contacts.js must define onContactSearchInput handler"


# --- SEARCH-02: Count banner ---

def test_count_banner_search_format():
    """buildCountBanner shows 'contacts match' text when search is active."""
    content = _read_pwa_file('js/contacts.js')
    assert 'contacts match' in content, "contacts.js buildCountBanner must include 'contacts match' text for search mode"


# --- SEARCH-01/02: Placeholder copy ---

def test_search_placeholder():
    """Search input has 'Search contacts...' placeholder text."""
    content = _read_pwa_file('js/contacts.js')
    assert 'Search contacts...' in content, "contacts.js must use 'Search contacts...' placeholder"


# --- SEARCH-01/02: Clear filters resets searchQuery ---

def test_clear_filters_resets_search():
    """clearContactFilters() resets searchQuery to empty string."""
    content = _read_pwa_file('js/contacts.js')
    # Verify clearContactFilters function resets searchQuery to empty string
    match = re.search(r'clearContactFilters.*?searchQuery\s*[:=]\s*[\'\"]\s*[\'\"]', content, re.DOTALL)
    assert match is not None, "clearContactFilters() must reset searchQuery to empty string ''"


# --- Input type="search" for native clear button ---

def test_search_input_type():
    """Search input uses type='search' for native browser clear button support."""
    content = _read_pwa_file('js/contacts.js')
    has_search_type = 'type="search"' in content or 'type=\\"search\\"' in content
    assert has_search_type, "contacts.js must use type=\"search\" input for native clear button"


# --- Cleanup: datalist removed ---

def test_role_datalist_removed():
    """contacts.js does NOT reference role-suggestions datalist (removed in Phase 14)."""
    content = _read_pwa_file('js/contacts.js')
    assert 'role-suggestions' not in content, "contacts.js must NOT reference role-suggestions datalist (removed in Phase 14)"


# --- Search icon SVG ---

def test_search_icon_svg():
    """contacts.js includes search-icon-svg SVG element for magnifying glass icon."""
    content = _read_pwa_file('js/contacts.js')
    assert 'search-icon-svg' in content, "contacts.js must include search-icon-svg class for search icon"
