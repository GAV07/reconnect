/* Reconnect PWA — App shell, router, Supabase client init */

// Config — set these to your Supabase project values
const SUPABASE_URL = window.RECONNECT_CONFIG?.supabaseUrl || '';
const SUPABASE_ANON_KEY = window.RECONNECT_CONFIG?.supabaseAnonKey || '';

let db = null;

function initSupabase() {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    console.warn('Supabase not configured. Set RECONNECT_CONFIG in index.html.');
    return;
  }
  db = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}

// Simple hash-based router
const routes = {
  '/search': { module: 'search', title: 'Search' },
  '/queue': { module: 'queue', title: 'Queue' },
  '/contacts': { module: 'contacts', title: 'Contacts' },
  '/contact': { module: 'contact', title: 'Contact' },
  '/dashboard': { module: 'dashboard', title: 'Dashboard' },
  '/pipeline': { module: 'pipeline', title: 'Pipeline' },
  '/preferences': { module: 'preferences', title: 'Preferences' },
};

function navigate(hash) {
  window.location.hash = hash;
}

function getRoute() {
  const hash = window.location.hash || '#/search';
  const path = hash.replace('#', '').split('?')[0];

  // Check for parameterized routes
  if (path.startsWith('/contact/')) {
    return { ...routes['/contact'], params: { id: path.split('/contact/')[1] } };
  }

  return routes[path] || routes['/search'];
}

function getQueryParams() {
  const hash = window.location.hash || '';
  const qIndex = hash.indexOf('?');
  if (qIndex === -1) return {};
  const params = new URLSearchParams(hash.substring(qIndex + 1));
  return Object.fromEntries(params);
}

async function render() {
  const route = getRoute();
  const content = document.getElementById('app-content');
  const headerTitle = document.querySelector('.app-header h1');
  const headerSub = document.querySelector('.app-header .subtitle');

  if (!content) return;

  // Update header
  if (headerTitle) headerTitle.textContent = route.title || 'Reconnect';
  if (headerSub) headerSub.textContent = '';

  // Update nav active state
  document.querySelectorAll('.bottom-nav a').forEach(a => {
    const href = a.getAttribute('href');
    const currentPath = (window.location.hash || '#/search').split('?')[0];
    a.classList.toggle('active', href === currentPath || (currentPath.startsWith('#/contact/') && href === '#/search'));
  });

  // Show loading
  content.innerHTML = '<div class="loading"><div class="spinner"></div> Loading...</div>';

  // Route to module
  try {
    switch (route.module) {
      case 'search':
        await renderSearch(content);
        break;
      case 'queue':
        await renderQueue(content);
        break;
      case 'contacts':
        await renderContacts(content);
        break;
      case 'contact':
        await renderContact(content, route.params?.id);
        break;
      case 'dashboard':
        await renderDashboard(content);
        break;
      case 'pipeline':
        await renderPipeline(content);
        break;
      case 'preferences':
        await renderPreferences(content);
        break;
      default:
        await renderSearch(content);
    }
  } catch (err) {
    console.error('Render error:', err);
    content.innerHTML = `<div class="empty-state"><div class="icon">&#9888;</div><p>Something went wrong. Check console for details.</p></div>`;
  }
}

// Offline detection
function setupOfflineDetection() {
  const banner = document.getElementById('offline-banner');
  if (!banner) return;

  window.addEventListener('online', () => banner.classList.remove('visible'));
  window.addEventListener('offline', () => banner.classList.add('visible'));
  if (!navigator.onLine) banner.classList.add('visible');
}

// Deep link bridge: reads query params and converts to hash route.
// Gmail's redirect chain strips hash fragments (RFC 3986), so emails must use
// query params for deep links. This function bridges them to the hash router.
//
// Supported deep links:
//   ?view=contact&id=X  → #/contact/X  (profile page)
//   ?view=queue         → #/queue      (queue page, from "Review in App" CTA)
function checkDeepLinkQueryParams() {
  const params = new URLSearchParams(window.location.search);
  const view = params.get('view');
  const id = params.get('id');
  if (view === 'contact' && id) {
    // Clean query params from URL bar, then set hash route
    history.replaceState(null, '', window.location.pathname);
    window.location.hash = `/contact/${id}`;
    return true; // hashchange event will trigger render()
  }
  if (view === 'queue') {
    history.replaceState(null, '', window.location.pathname);
    window.location.hash = '/queue';
    return true;
  }
  if (view === 'search') {
    history.replaceState(null, '', window.location.pathname);
    window.location.hash = '/search';
    return true;
  }
  return false;
}

// Init
document.addEventListener('DOMContentLoaded', () => {
  initSupabase();
  setupOfflineDetection();
  if (!checkDeepLinkQueryParams()) {
    render(); // only call render() if we didn't trigger a hashchange
  }
});

window.addEventListener('hashchange', render);

// Register service worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('service-worker.js')
    .then(reg => console.log('SW registered:', reg.scope))
    .catch(err => console.warn('SW registration failed:', err));
}
