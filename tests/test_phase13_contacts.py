"""Phase 13 Contacts Browse Page validation tests.

Tests verify PWA static files contain expected patterns for BROWSE-01 through BROWSE-05.
Uses Python open() + string matching — same pattern as tests/test_phase3_pwa.py.
"""

import os
import re

PWA_DIR = os.path.join(os.path.dirname(__file__), '..', 'pwa')


def _read_pwa_file(relative_path):
    """Read a PWA file and return its contents."""
    path = os.path.join(PWA_DIR, relative_path)
    with open(path, 'r') as f:
        return f.read()


# --- BROWSE-01: Contacts page exists and is wired ---

def test_contacts_js_exists():
    """contacts.js file exists in pwa/js/ directory."""
    path = os.path.join(PWA_DIR, 'js', 'contacts.js')
    assert os.path.exists(path), f'Missing file: {path}'
    content = _read_pwa_file('js/contacts.js')
    assert 'renderContacts' in content, 'contacts.js must export a renderContacts function'


def test_contacts_route_registered():
    """app.js routes object contains /contacts entry."""
    content = _read_pwa_file('js/app.js')
    assert "'/contacts'" in content, "app.js must have '/contacts' in routes object"
    assert "case 'contacts'" in content, "app.js render() must have case 'contacts'"
    assert 'renderContacts' in content, "app.js must call renderContacts in switch"


def test_nav_has_contacts_tab():
    """index.html bottom-nav has 4 tabs with Contacts as 2nd tab."""
    content = _read_pwa_file('index.html')
    # Verify the contacts nav link exists
    assert 'href="#/contacts"' in content, 'index.html must have href="#/contacts" in nav'
    # Verify contacts.js is loaded
    assert 'js/contacts.js' in content, 'index.html must load js/contacts.js'
    # Verify 4 nav items by counting href occurrences in bottom-nav section
    nav_start = content.index('class="bottom-nav"')
    nav_end = content.index('</nav>', nav_start)
    nav_html = content[nav_start:nav_end]
    href_count = nav_html.count('href=')
    assert href_count == 4, f'Expected 4 nav tabs, got {href_count}'


# --- BROWSE-02: Role/title filter ---

def test_role_filter_exists():
    """contacts.js has text-based search/filter input (role filter or search bar)."""
    content = _read_pwa_file('js/contacts.js')
    has_role = 'roleQuery' in content
    has_search = 'searchQuery' in content
    assert has_role or has_search, 'contacts.js must have roleQuery or searchQuery filter state'


# --- BROWSE-03: Industry filter ---

def test_industry_filter_exists():
    """contacts.js has industry filter that uses enriched_industry column."""
    content = _read_pwa_file('js/contacts.js')
    assert 'industryFilter' in content, 'contacts.js must have industryFilter state'
    assert 'enriched_industry' in content, 'contacts.js must query enriched_industry column'


# --- BROWSE-04: Location filter ---

def test_city_filter_exists():
    """contacts.js has city filter that uses enriched_city column."""
    content = _read_pwa_file('js/contacts.js')
    assert 'cityFilter' in content, 'contacts.js must have cityFilter state'
    assert 'enriched_city' in content, 'contacts.js must query enriched_city column'


# --- BROWSE-05: Server-side pagination + explicit field selection ---

def test_browse_select_excludes_raw_enrichment():
    """BROWSE_SELECT constant exists and does NOT include raw_enrichment."""
    content = _read_pwa_file('js/contacts.js')
    assert 'BROWSE_SELECT' in content, 'contacts.js must define BROWSE_SELECT constant'
    assert 'raw_enrichment' not in content, 'contacts.js must NEVER reference raw_enrichment'


def test_page_size_is_50():
    """Pagination uses page size of 50 (offset + 49 pattern)."""
    content = _read_pwa_file('js/contacts.js')
    assert '49' in content, 'contacts.js must use offset + 49 for .range() (page size 50)'
    assert '.range(' in content, 'contacts.js must call .range() for server-side pagination'


def test_contact_filters_shape():
    """contactFilters object has text filter (roleQuery or searchQuery), industryFilter, and cityFilter."""
    content = _read_pwa_file('js/contacts.js')
    assert 'contactFilters' in content, 'contacts.js must define contactFilters object'
    has_role = 'roleQuery' in content
    has_search = 'searchQuery' in content
    assert has_role or has_search, 'contactFilters must have roleQuery or searchQuery'
    assert 'industryFilter' in content, 'contactFilters must have industryFilter'
    assert 'cityFilter' in content, 'contactFilters must have cityFilter'
    assert 'offset' in content, 'contactFilters must have offset'
    assert 'totalCount' in content, 'contactFilters must have totalCount'


def test_count_exact_used():
    """Uses count: 'exact' for total count in same request."""
    content = _read_pwa_file('js/contacts.js')
    assert "count" in content and "exact" in content, "contacts.js must use count: 'exact' option"


def test_order_by_score_descending():
    """Default sort is reconnect_score descending."""
    content = _read_pwa_file('js/contacts.js')
    assert 'reconnect_score' in content, 'contacts.js must sort by reconnect_score'
    assert 'ascending: false' in content or 'ascending:false' in content, 'contacts.js must sort descending'


def test_excludes_archived_contacts():
    """Query excludes archived contacts (user_priority = 'never')."""
    content = _read_pwa_file('js/contacts.js')
    assert 'user_priority' in content, 'contacts.js must filter on user_priority'
    assert 'never' in content, "contacts.js must exclude user_priority='never'"
