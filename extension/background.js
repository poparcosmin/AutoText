// Import configuration
importScripts('config.js');

const DEBUG = false;
const debugLog = (...args) => {
  if (DEBUG) {
    console.log(...args);
  }
};

// Offline/Online status tracking
let isOnline = true;

// Sync retry policy — fixed-delay retries via chrome.alarms (survives SW restarts).
// Deliberately NOT exponential backoff: MV3 service workers can be killed before
// long delays elapse, losing state. 1 min is the practical minimum for MV3 alarms.
const MAX_SYNC_RETRIES = 3;
const RETRY_DELAY_MINUTES = 1;

async function markSyncSuccess() {
  await chrome.storage.local.remove([
    'sync_retry_count', 'sync_error', 'sync_error_time'
  ]);
  try { await chrome.alarms.clear('syncRetry'); } catch (_) { /* noop */ }
  await chrome.storage.local.set({ sync_status: 'success' });
}

async function markSyncFailure(errorMessage) {
  const stored = await chrome.storage.local.get('sync_retry_count');
  const attempt = (stored.sync_retry_count || 0) + 1;

  await chrome.storage.local.set({
    sync_status: 'error',
    sync_error: errorMessage,
    sync_error_time: Date.now(),
    sync_retry_count: attempt,
  });

  if (attempt < MAX_SYNC_RETRIES) {
    chrome.alarms.create('syncRetry', { delayInMinutes: RETRY_DELAY_MINUTES });
    debugLog(`AutoText: Sync failed (attempt ${attempt}/${MAX_SYNC_RETRIES}), retry in ${RETRY_DELAY_MINUTES} min`);
  } else {
    // Final failure — user-visible red badge, clear retry counter so next success restores green
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#F44336' });
    chrome.action.setTitle({
      title: `AutoText - Sync failed after ${MAX_SYNC_RETRIES} attempts. Click for options.`
    });
    debugLog(`AutoText: Sync failed ${MAX_SYNC_RETRIES} times — giving up, red badge shown`);
  }
}

// NOTE: Service Worker lifecycle is event-driven in Manifest V3
// The worker will naturally sleep between events - this is expected behavior.
// We rely on chrome.alarms for periodic sync (see initializeListeners).
// DO NOT use setInterval keep-alive hacks - they don't work reliably in MV3
// and may be terminated by the browser at any time.

/**
 * Update online/offline status and badge
 */
async function updateOnlineStatus(online) {
  isOnline = online;

  if (!online) {
    // Offline - show indicator
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
    chrome.action.setTitle({ title: 'AutoText - Offline (using cached shortcuts)' });
    debugLog('AutoText: Now offline, using cached shortcuts');
  } else {
    // Online - clear offline indicator and sync
    await updateBadgeWithShortcutCount();
    chrome.action.setTitle({ title: 'AutoText' });
    debugLog('AutoText: Now online, attempting sync...');
    syncShortcuts();
  }
}

/**
 * Update badge with shortcut count
 */
async function updateBadgeWithShortcutCount() {
  try {
    const { shortcuts } = await chrome.storage.local.get('shortcuts');
    const count = shortcuts ? Object.keys(shortcuts).length : 0;

    if (count > 0) {
      chrome.action.setBadgeText({ text: count.toString() });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    } else {
      chrome.action.setBadgeText({ text: '' });
    }
  } catch (error) {
    console.error('AutoText: Error updating badge:', error);
  }
}

// Check and refresh token if needed (30 days before expiration)
async function checkAndRefreshToken() {
  try {
    const { auth_token, token_expires_at } = await chrome.storage.local.get([
      'auth_token',
      'token_expires_at'
    ]);

    if (!auth_token || !token_expires_at) return;

    const expiresAt = new Date(token_expires_at);
    const now = new Date();
    const daysUntilExpiry = (expiresAt - now) / (1000 * 60 * 60 * 24);

    // Refresh if within 30 days of expiration
    if (daysUntilExpiry <= 30 && daysUntilExpiry > 0) {
      debugLog(`AutoText: Token expires in ${Math.floor(daysUntilExpiry)} days, attempting refresh...`);

      const res = await fetch(`${CONFIG.API_URL}/auth/refresh/`, {
        method: 'POST',
        headers: {
          'Authorization': `Token ${auth_token}`,
          'Content-Type': 'application/json'
        }
      });

      if (res.ok) {
        const data = await res.json();
        await chrome.storage.local.set({
          auth_token: data.token,
          token_expires_at: data.expires_at
        });
        debugLog('AutoText: Token refreshed successfully');
      }
    }
  } catch (error) {
    console.error('AutoText: Token refresh failed:', error);
  }
}

// Pull the user's custom variables ([[var:name]]) and cache them locally.
// Best-effort: on failure we don't abort the whole sync, just leave stale
// values; users can still expand other shortcuts. Variables are tiny (<1KB
// per user typically) so a full re-fetch is cheaper than delta tracking.
async function syncUserVariables(authToken) {
  if (!authToken) return;
  try {
    const res = await fetch(`${CONFIG.API_URL}/user-variables/`, {
      headers: { 'Authorization': `Token ${authToken}` }
    });
    if (!res.ok) {
      // 401 is handled by the main syncShortcuts flow; quietly skip here.
      debugLog(`AutoText: user-variables fetch returned ${res.status}, skipping`);
      return;
    }
    const list = await res.json();
    const map = {};
    for (const item of list) {
      if (item && item.name) map[item.name] = item.value || '';
    }
    await chrome.storage.local.set({ userVariables: map });
    debugLog(`AutoText: synced ${list.length} user variable(s)`);
  } catch (err) {
    debugLog('AutoText: user-variables sync failed:', err && err.message);
  }
}

// Sync shortcuts from Django backend with multi-set support and authentication
// Uses bulk sync endpoint for better performance (single API call)
// Supports offline mode - uses cached shortcuts when network unavailable
async function syncShortcuts() {
  debugLog("AutoText Background: syncShortcuts() called");

  // Check if we're offline
  if (!navigator.onLine) {
    debugLog("AutoText: Device is offline, skipping sync");
    updateOnlineStatus(false);
    return;
  }

  try {
    // Check token refresh before sync
    await checkAndRefreshToken();

    let { auth_token, active_sets, last_sync, shortcuts } = await chrome.storage.local.get([
      "auth_token",
      "active_sets",
      "last_sync",
      "shortcuts"
    ]);

    // Log only non-sensitive info
    debugLog("AutoText: Storage retrieved:", {
      has_token: !!auth_token,
      sets_count: active_sets ? active_sets.length : 0,
      has_last_sync: !!last_sync
    });

    // Check if user is authenticated — silent skip, no OS popup.
    // User can login from Options page when they choose to.
    if (!auth_token) {
      debugLog("AutoText: No auth token — sync skipped silently. Login via Options to sync.");
      return;
    }

    // Force full sync if storage is empty (even if last_sync exists)
    const shortcutsCount = shortcuts ? Object.keys(shortcuts).length : 0;
    if (shortcutsCount === 0 && last_sync) {
      debugLog("AutoText: Storage is empty but last_sync exists, forcing full sync...");
      await chrome.storage.local.remove('last_sync');
      last_sync = null;
    }

    // Get active sets (default to 'birou' if none selected)
    const sets = active_sets || ['birou'];
    debugLog(`AutoText: Syncing shortcuts from ${sets.length} set(s)`);

    // Use bulk sync endpoint for better performance
    const bulkSyncUrl = `${CONFIG.API_URL}/sync/bulk/`;
    const isDeltaSync = !!last_sync;

    const requestBody = {
      sets: sets,
    };

    if (last_sync) {
      requestBody.updated_after = new Date(last_sync).toISOString();
    }

    debugLog(`AutoText: Syncing (${isDeltaSync ? 'delta' : 'full'}) via bulk endpoint`);

    const res = await fetch(bulkSyncUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${auth_token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    });

    // Handle authentication errors
    if (res.status === 401) {
      console.error("AutoText: Authentication failed - token expired or invalid");
      await handleAuthenticationFailure();
      return;
    }

    // Handle rate limiting
    if (res.status === 429) {
      console.warn("AutoText: Rate limited, will retry later");
      return;
    }

    if (!res.ok) {
      const errorText = await res.text();
      console.error("AutoText: Failed to sync shortcuts:", res.status, res.statusText);
      console.error("AutoText: Error details:", errorText);
      await markSyncFailure(`HTTP ${res.status}: ${res.statusText}`);
      return;
    }

    const syncData = await res.json();
    debugLog(`AutoText: Received ${syncData.count.shortcuts} shortcuts, ${syncData.count.sets} sets from server`);

    // If delta sync and we have existing shortcuts, merge with them
    let shortcutsMap;
    if (last_sync && syncData.shortcuts.length > 0) {
      // Delta sync - merge with existing shortcuts
      const { shortcuts: existingShortcuts } = await chrome.storage.local.get('shortcuts');
      const existingMap = existingShortcuts || {};

      // Update existing map with new/changed shortcuts
      const newShortcutsMap = mergeShortcutsWithPriority(syncData.shortcuts);
      shortcutsMap = { ...existingMap, ...newShortcutsMap };

      debugLog(`AutoText: Delta sync - merged ${syncData.shortcuts.length} changes with existing shortcuts`);
    } else {
      // Full sync - replace all shortcuts
      shortcutsMap = mergeShortcutsWithPriority(syncData.shortcuts);
      debugLog(`AutoText: Full sync - loaded ${Object.keys(shortcutsMap).length} shortcuts`);
    }

    // Store indexed shortcuts, sets info, and sync timestamp
    await chrome.storage.local.set({
      shortcuts: shortcutsMap,
      available_sets: syncData.sets,
      last_sync: Date.now(),
      server_time: syncData.server_time,
      sync_status: 'success'
    });

    // Update badge with shortcut count (this also clears any red-badge retry state)
    await markSyncSuccess();
    await updateBadgeWithShortcutCount();

    // Pull latest user variables alongside shortcuts so [[var:name]] resolves
    // against fresh values on the next expansion.
    await syncUserVariables(auth_token);

    debugLog(`AutoText: Sync complete. Total shortcuts: ${Object.keys(shortcutsMap).length}`);
  } catch (error) {
    console.error("AutoText: Error during sync:", error);

    // Check if it's a network error (offline)
    if (error.message && (error.message.includes('Failed to fetch') || error.message.includes('NetworkError'))) {
      updateOnlineStatus(false);
    }

    await markSyncFailure(error.message || 'Unknown sync error');
  }
}

/**
 * Handle authentication failure (401) — clears auth silently.
 * No OS notification: the popup and Options page surface auth state;
 * nagging notifications on every sync cycle was hostile UX.
 */
async function handleAuthenticationFailure() {
  await chrome.storage.local.remove(['auth_token', 'username']);
  debugLog("AutoText: Auth token cleared after 401. Login via Options when ready.");
}

/**
 * Merge shortcuts with conflict resolution
 * Rule: Personal sets take priority over general sets
 *
 * Example:
 *   - shortcut1: key='b', sets=['birou'], set_types=['general']
 *   - shortcut2: key='b', sets=['cosmin'], set_types=['personal']
 *   Result: Use shortcut2 (personal > general)
 */
function mergeShortcutsWithPriority(shortcuts) {
  const map = {};

  shortcuts.forEach(shortcut => {
    const hasPersonal = shortcut.set_types && shortcut.set_types.includes('personal');
    const entry = {
      value: shortcut.value,
      html_value: shortcut.html_value,
      id: shortcut.id,
      sets: shortcut.set_names || [],
      is_personal: hasPersonal,
      // Optional alternative bodies; content.js rolls a random pick
      // across [primary, ...variants] at expand time.
      variants: shortcut.variants || [],
      // Primary key recorded so the alias entries know which row they
      // mirror; useful when restoring or counting.
      primary_key: shortcut.key,
    };

    // Build the trigger list = primary key + each alias. Aliases inherit
    // the same priority as the primary, so personal beats general for
    // either form.
    const triggers = [shortcut.key, ...(shortcut.aliases || [])].filter(Boolean);

    triggers.forEach(key => {
      if (!map[key]) {
        map[key] = entry;
        return;
      }
      // Key collision — apply personal-wins priority. If both are at the
      // same priority, the first arrival keeps the slot (API ordering
      // controls the tiebreaker).
      const existingIsPersonal = map[key].is_personal;
      if (hasPersonal && !existingIsPersonal) {
        debugLog(`AutoText: Replacing '${key}' with personal version`);
        map[key] = entry;
      }
    });
  });

  return map;
}

// Initialize event listeners (called on startup and when service worker wakes up)
function initializeListeners() {
  debugLog("AutoText: Initializing event listeners...");

  // Periodic sync every 5 minutes using chrome.alarms (MV3-compliant)
  // The alarm will wake up the service worker when it fires
  chrome.alarms.create("syncShortcuts", { periodInMinutes: 5 });
}

// Sync on extension startup
chrome.runtime.onStartup.addListener(() => {
  debugLog("AutoText: Extension started, syncing shortcuts...");
  initializeListeners();
  syncShortcuts();
});

// Sync on extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  debugLog("AutoText: Extension installed/updated, syncing shortcuts...");
  initializeListeners();
  syncShortcuts();
});

// Alarm listener (must be at top level, not inside function)
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "syncShortcuts") {
    debugLog("AutoText: Periodic sync triggered");
    syncShortcuts();
  } else if (alarm.name === "syncRetry") {
    debugLog("AutoText: Retry sync triggered");
    syncShortcuts();
  }
});

// Keyboard command listener
chrome.commands.onCommand.addListener(async (command) => {
  debugLog("AutoText: Command received:", command);

  switch (command) {
    case "sync-shortcuts":
      // Manual sync via keyboard shortcut
      debugLog("AutoText: Manual sync triggered via keyboard");
      await syncShortcuts();
      chrome.notifications.create('autotext-sync', {
        type: 'basic',
        iconUrl: 'icon48.png',
        title: 'AutoText - Sync Complete',
        message: 'Shortcuts have been synchronized.',
        priority: 0
      });
      break;

    case "toggle-autotext":
      // Toggle AutoText enabled/disabled
      const { autotext_enabled } = await chrome.storage.local.get('autotext_enabled');
      const newState = autotext_enabled === false ? true : false;
      await chrome.storage.local.set({ autotext_enabled: !autotext_enabled });

      // Update badge to show state
      if (newState) {
        await updateBadgeWithShortcutCount();
        chrome.action.setTitle({ title: 'AutoText - Active' });
      } else {
        chrome.action.setBadgeText({ text: 'OFF' });
        chrome.action.setBadgeBackgroundColor({ color: '#9E9E9E' });
        chrome.action.setTitle({ title: 'AutoText - Disabled' });
      }

      chrome.notifications.create('autotext-toggle', {
        type: 'basic',
        iconUrl: 'icon48.png',
        title: newState ? 'AutoText Enabled' : 'AutoText Disabled',
        message: newState ? 'Text expansion is now active.' : 'Text expansion is paused.',
        priority: 0
      });
      break;

    case "open-options":
      // Open options page
      chrome.runtime.openOptionsPage();
      break;

    case "open-palette": {
      // Forward to the active tab's content script (it owns the overlay)
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (tab && tab.id) {
        chrome.tabs.sendMessage(tab.id, { action: 'openPalette' }).catch(() => {
          // Tab has no content script (chrome:// pages etc.) — ignore.
        });
      }
      break;
    }
  }
});

// Manual sync trigger and status queries (must be at top level)
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  // Only accept messages from our own extension contexts (popup, options,
  // content scripts). Without this, any script via externally_connectable
  // could invoke privileged actions. OWASP Browser Extension cheat sheet.
  if (sender.id !== chrome.runtime.id) {
    debugLog("AutoText Background: rejected message from sender.id=", sender.id);
    return false;
  }

  debugLog("AutoText Background: Received message:", req);

  if (req.action === "sync") {
    debugLog("AutoText Background: Starting manual sync...");
    syncShortcuts().then(() => {
      debugLog("AutoText Background: Sync completed, sending response");
      sendResponse({ status: "done" });
    }).catch(error => {
      console.error("AutoText Background: Sync failed:", error);
      sendResponse({ status: "error", message: error.message });
    });
    return true; // Keep message channel open for async response
  }

  if (req.action === "getStatus") {
    // Return current status for popup/options
    chrome.storage.local.get([
      'shortcuts', 'last_sync', 'sync_status', 'sync_error', 'active_sets'
    ]).then(data => {
      sendResponse({
        online: navigator.onLine,
        shortcutCount: data.shortcuts ? Object.keys(data.shortcuts).length : 0,
        lastSync: data.last_sync,
        syncStatus: data.sync_status,
        syncError: data.sync_error,
        activeSets: data.active_sets || []
      });
    });
    return true;
  }

  if (req.action === "updateBadge") {
    updateBadgeWithShortcutCount().then(() => {
      sendResponse({ status: "done" });
    });
    return true;
  }
});

// Initialize on service worker load
debugLog("AutoText Background: Service worker initialized");
initializeListeners();

// Initialize badge on load
updateBadgeWithShortcutCount();

// Check initial online status
if (!navigator.onLine) {
  updateOnlineStatus(false);
}
