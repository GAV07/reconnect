/* Offline support — IndexedDB cache + Background Sync */

const DB_NAME = 'reconnect-offline';
const DB_VERSION = 1;
const PENDING_ACTIONS_STORE = 'pending_actions';
const CACHE_STORE = 'cache';

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(PENDING_ACTIONS_STORE)) {
        db.createObjectStore(PENDING_ACTIONS_STORE, { keyPath: 'id', autoIncrement: true });
      }
      if (!db.objectStoreNames.contains(CACHE_STORE)) {
        db.createObjectStore(CACHE_STORE, { keyPath: 'key' });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function queueOfflineAction(action) {
  try {
    const db = await openDB();
    const tx = db.transaction(PENDING_ACTIONS_STORE, 'readwrite');
    tx.objectStore(PENDING_ACTIONS_STORE).add(action);
    await new Promise((resolve, reject) => {
      tx.oncomplete = resolve;
      tx.onerror = reject;
    });

    // Request Background Sync if available
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      const reg = await navigator.serviceWorker.ready;
      await reg.sync.register('sync-actions');
    }

    console.log('Action queued for offline sync:', action);
  } catch (err) {
    console.error('Failed to queue offline action:', err);
  }
}

async function getPendingActions() {
  try {
    const db = await openDB();
    const tx = db.transaction(PENDING_ACTIONS_STORE, 'readonly');
    const store = tx.objectStore(PENDING_ACTIONS_STORE);
    return new Promise((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  } catch {
    return [];
  }
}

async function clearPendingAction(id) {
  try {
    const db = await openDB();
    const tx = db.transaction(PENDING_ACTIONS_STORE, 'readwrite');
    tx.objectStore(PENDING_ACTIONS_STORE).delete(id);
  } catch (err) {
    console.error('Failed to clear pending action:', err);
  }
}

async function replayPendingActions() {
  if (!supabase || !navigator.onLine) return;

  const actions = await getPendingActions();
  for (const action of actions) {
    try {
      const statusMap = { approve: 'approved', skip: 'skipped', snooze: 'skipped' };
      const newStatus = statusMap[action.action];
      const skipReason = action.action === 'snooze' ? 'Snoozed via PWA (3 day cooldown)' : (action.action === 'skip' ? 'Skipped via PWA' : null);

      const updateData = { status: newStatus, reviewed_at: new Date(action.timestamp).toISOString() };
      if (skipReason) updateData.skip_reason = skipReason;

      const { error } = await supabase
        .from('outreach_queue')
        .update(updateData)
        .eq('id', action.itemId);

      if (!error) {
        await clearPendingAction(action.id);
        console.log('Replayed offline action:', action);
      }
    } catch (err) {
      console.error('Failed to replay action:', err);
    }
  }
}

// Replay when coming back online
window.addEventListener('online', () => {
  replayPendingActions();
});

// Cache data for offline use
async function cacheData(key, data) {
  try {
    const db = await openDB();
    const tx = db.transaction(CACHE_STORE, 'readwrite');
    tx.objectStore(CACHE_STORE).put({ key, data, cachedAt: Date.now() });
  } catch (err) {
    console.error('Cache write failed:', err);
  }
}

async function getCachedData(key) {
  try {
    const db = await openDB();
    const tx = db.transaction(CACHE_STORE, 'readonly');
    return new Promise((resolve) => {
      const request = tx.objectStore(CACHE_STORE).get(key);
      request.onsuccess = () => resolve(request.result?.data || null);
      request.onerror = () => resolve(null);
    });
  } catch {
    return null;
  }
}
