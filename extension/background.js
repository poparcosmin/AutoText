// Import configuration
importScripts('config.js');

// Use CONFIG.API_URL and CONFIG.DEV_TOKEN from config.js

// Sync shortcuts from Django backend with multi-set support
async function syncShortcuts() {
  try {
    let { auth_token, active_sets, api_url } = await chrome.storage.local.get([
      "auth_token",
      "active_sets",
      "api_url"
    ]);

    // Auto-set token for development if not present
    if (!auth_token) {
      console.log("AutoText: No token found, using development token...");
      auth_token = CONFIG.DEV_TOKEN;
      await chrome.storage.local.set({ auth_token: CONFIG.DEV_TOKEN });
      console.log("AutoText: Development token saved to storage.");
    }

    // Get active sets (default to 'birou' if none selected)
    const sets = active_sets || ['birou'];
    console.log(`AutoText: Syncing shortcuts from sets: ${sets.join(', ')}`);

    // Build API URL with sets query parameter
    const baseUrl = api_url || `${CONFIG.API_URL}/shortcuts/`;
    const setsParam = sets.join(',');
    const url = `${baseUrl}?sets=${encodeURIComponent(setsParam)}`;

    console.log(`AutoText: Fetching from: ${url}`);

    const res = await fetch(url, {
      headers: { Authorization: `Token ${auth_token}` }
    });

    if (!res.ok) {
      console.error("AutoText: Failed to sync shortcuts:", res.status, res.statusText);
      return;
    }

    const serverShortcuts = await res.json();
    console.log(`AutoText: Received ${serverShortcuts.length} shortcuts from server`);

    // Merge shortcuts with conflict resolution (personal > general)
    const shortcutsMap = mergeShortcutsWithPriority(serverShortcuts);

    // Store indexed shortcuts and sync timestamp
    await chrome.storage.local.set({
      shortcuts: shortcutsMap,
      last_sync: Date.now()
    });

    console.log(`AutoText: Synced ${Object.keys(shortcutsMap).length} unique shortcuts (after conflict resolution)`);
  } catch (error) {
    console.error("AutoText: Error during sync:", error);
  }
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
    const key = shortcut.key;

    // Check if this shortcut belongs to a personal set
    const hasPersonal = shortcut.set_types && shortcut.set_types.includes('personal');

    // If key doesn't exist yet, add it
    if (!map[key]) {
      map[key] = {
        value: shortcut.value,
        html_value: shortcut.html_value,
        id: shortcut.id,
        sets: shortcut.set_names || [],
        is_personal: hasPersonal
      };
    } else {
      // Key already exists - check priority
      const existingIsPersonal = map[key].is_personal;

      // If current shortcut is personal and existing isn't, replace it
      if (hasPersonal && !existingIsPersonal) {
        console.log(`AutoText: Replacing '${key}' with personal version`);
        map[key] = {
          value: shortcut.value,
          html_value: shortcut.html_value,
          id: shortcut.id,
          sets: shortcut.set_names || [],
          is_personal: hasPersonal
        };
      }
      // If both are personal or both are general, keep the first one
      // (API should not return duplicates at same priority level, but just in case)
    }
  });

  return map;
}

// Sync on extension startup
chrome.runtime.onStartup.addListener(() => {
  console.log("AutoText: Extension started, syncing shortcuts...");
  syncShortcuts();
});

// Sync on extension installation/update
chrome.runtime.onInstalled.addListener(() => {
  console.log("AutoText: Extension installed/updated, syncing shortcuts...");
  syncShortcuts();
});

// Periodic sync every 5 minutes (300000 ms)
chrome.alarms.create("syncShortcuts", { periodInMinutes: 5 });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "syncShortcuts") {
    console.log("AutoText: Periodic sync triggered");
    syncShortcuts();
  }
});

// Manual sync trigger (can be called from content script if needed)
chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
  if (req.action === "sync") {
    syncShortcuts().then(() => sendResponse({ status: "done" }));
    return true;
  }
});
