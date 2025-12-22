// AutoText Content Script - Core text expansion logic
// Listens for Tab key, detects shortcuts, and replaces with expansions

const DEBUG = false;
const debugLog = (...args) => {
  if (DEBUG) {
    console.log(...args);
  }
};

let shortcuts = {};
let autotextEnabled = true;  // Global toggle state
let settings = {
  triggerKey: 'Tab',
  showToast: true,
  showHighlight: true,
  playSound: false,
  blacklistedSites: []
};

// Load settings from storage
async function loadSettings() {
  try {
    const result = await chrome.storage.local.get(['settings', 'autotext_enabled']);
    if (result.settings) {
      settings = { ...settings, ...result.settings };
    }
    // Load global enabled state (default to true if not set)
    autotextEnabled = result.autotext_enabled !== false;
  } catch (error) {
    console.error('AutoText: Error loading settings:', error);
  }
}

// Check if current site is blacklisted
function isBlacklisted() {
  const hostname = window.location.hostname;
  return settings.blacklistedSites.some(site =>
    hostname.includes(site) || site.includes(hostname)
  );
}

// Create and inject styles for visual feedback
function injectFeedbackStyles() {
  if (document.getElementById('autotext-styles')) return;

  const style = document.createElement('style');
  style.id = 'autotext-styles';
  style.textContent = `
    @keyframes autotext-highlight {
      0% { background-color: rgba(76, 175, 80, 0.4); }
      100% { background-color: transparent; }
    }

    @keyframes autotext-toast-in {
      from { opacity: 0; transform: translateY(20px) scale(0.9); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    @keyframes autotext-toast-out {
      from { opacity: 1; transform: translateY(0) scale(1); }
      to { opacity: 0; transform: translateY(-10px) scale(0.9); }
    }

    .autotext-highlight {
      animation: autotext-highlight 0.6s ease-out;
      border-radius: 2px;
    }

    .autotext-toast {
      position: fixed;
      bottom: 20px;
      right: 20px;
      background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      font-weight: 500;
      box-shadow: 0 4px 20px rgba(0,0,0,0.15), 0 2px 8px rgba(76,175,80,0.3);
      z-index: 2147483647;
      display: flex;
      align-items: center;
      gap: 10px;
      animation: autotext-toast-in 0.3s ease-out;
      max-width: 300px;
    }

    .autotext-toast.hiding {
      animation: autotext-toast-out 0.2s ease-in forwards;
    }

    .autotext-toast-icon {
      font-size: 18px;
    }

    .autotext-toast-content {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .autotext-toast-title {
      font-weight: 600;
    }

    .autotext-toast-shortcut {
      font-size: 12px;
      opacity: 0.9;
    }
  `;
  document.head.appendChild(style);
}

// Show toast notification (using safe DOM methods)
function showToast(shortcutKey, expansionPreview) {
  if (!settings.showToast) return;

  // Remove existing toast
  const existing = document.querySelector('.autotext-toast');
  if (existing) existing.remove();

  // Create toast container
  const toast = document.createElement('div');
  toast.className = 'autotext-toast';

  // Create icon span
  const iconSpan = document.createElement('span');
  iconSpan.className = 'autotext-toast-icon';
  iconSpan.textContent = '⚡';

  // Create content container
  const contentDiv = document.createElement('div');
  contentDiv.className = 'autotext-toast-content';

  // Create title span
  const titleSpan = document.createElement('span');
  titleSpan.className = 'autotext-toast-title';
  titleSpan.textContent = 'Expanded!';

  // Create shortcut span with preview
  const shortcutSpan = document.createElement('span');
  shortcutSpan.className = 'autotext-toast-shortcut';
  const preview = expansionPreview.length > 40
    ? expansionPreview.substring(0, 40) + '...'
    : expansionPreview;
  shortcutSpan.textContent = `${shortcutKey} → ${preview}`;

  // Assemble DOM tree
  contentDiv.appendChild(titleSpan);
  contentDiv.appendChild(shortcutSpan);
  toast.appendChild(iconSpan);
  toast.appendChild(contentDiv);

  document.body.appendChild(toast);

  // Auto-remove after 2 seconds
  setTimeout(() => {
    toast.classList.add('hiding');
    setTimeout(() => toast.remove(), 200);
  }, 2000);
}

// Play expansion sound
function playExpansionSound() {
  if (!settings.playSound) return;

  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.frequency.value = 800;
    oscillator.type = 'sine';
    gainNode.gain.value = 0.1;

    oscillator.start();
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
    oscillator.stop(audioContext.currentTime + 0.1);
  } catch (error) {
    // Audio not supported, ignore
  }
}

// Track shortcut usage for statistics
async function trackShortcutUsage(shortcutKey, shortcutId) {
  try {
    // Update local stats (for offline access and quick display)
    const result = await chrome.storage.local.get('shortcutStats');
    const stats = result.shortcutStats || {};

    if (!stats[shortcutKey]) {
      stats[shortcutKey] = { count: 0, lastUsed: null, id: shortcutId };
    }

    stats[shortcutKey].count++;
    stats[shortcutKey].lastUsed = Date.now();

    await chrome.storage.local.set({ shortcutStats: stats });

    // Send usage data to server for analytics (fire-and-forget)
    sendUsageToServer(shortcutId, window.location.hostname);
  } catch (error) {
    // Stats tracking failed, non-critical
  }
}

// Send usage data to server API for centralized analytics
async function sendUsageToServer(shortcutId, domain) {
  try {
    const authResult = await chrome.storage.local.get('authToken');
    if (!authResult.authToken) return;

    const serverResult = await chrome.storage.local.get('serverUrl');
    const serverUrl = serverResult.serverUrl || 'http://localhost:8000';

    // Fire-and-forget: don't await response to avoid blocking
    fetch(`${serverUrl}/api/track-usage/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${authResult.authToken}`
      },
      body: JSON.stringify({
        shortcut_id: shortcutId,
        domain: domain
      })
    }).catch(() => {
      // Silently fail - analytics are non-critical
    });
  } catch (error) {
    // Non-critical error, ignore
  }
}

// Load shortcuts from storage on initialization
async function loadShortcuts() {
  try {
    const result = await chrome.storage.local.get("shortcuts");
    shortcuts = result.shortcuts || {};
    debugLog("AutoText: Loaded", Object.keys(shortcuts).length, "shortcuts");

    // If no shortcuts found, trigger auto-sync from background
    if (Object.keys(shortcuts).length === 0) {
      debugLog("AutoText: No shortcuts found, triggering auto-sync...");
      chrome.runtime.sendMessage({ action: 'sync' }, (response) => {
        if (chrome.runtime.lastError) {
          console.error("AutoText: Failed to trigger sync:", chrome.runtime.lastError.message);
        } else {
          debugLog("AutoText: Auto-sync triggered successfully");
        }
      });
    }
  } catch (error) {
    console.error("AutoText: Error loading shortcuts:", error);
  }
}

// Listen for storage changes (when background syncs new shortcuts)
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.shortcuts) {
    shortcuts = changes.shortcuts.newValue || {};
    debugLog("AutoText: Shortcuts updated,", Object.keys(shortcuts).length, "available");
  }
});

// Get text before cursor in different element types
function getTextBeforeCursor(element) {
  // For input and textarea elements
  if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
    const cursorPos = element.selectionStart;

    // Validate cursor position
    if (cursorPos === null || cursorPos === undefined || cursorPos < 0) {
      debugLog("AutoText Debug: Invalid cursor position:", cursorPos);
      return "";
    }

    const fullValue = element.value;
    const textBefore = fullValue.substring(0, cursorPos);

    debugLog("AutoText Debug: INPUT/TEXTAREA", {
      fullValue,
      cursorPos,
      textBefore,
      valueLength: fullValue.length
    });

    // Extract the last word (everything after last space/newline)
    const match = textBefore.match(/(\S+)$/);
    let lastWord = match ? match[1] : "";

    // Clean zero-width characters and invisible Unicode characters
    lastWord = lastWord.replace(/[\u200B-\u200D\uFEFF]/g, '');

    debugLog("AutoText Debug: Extracted last word:", lastWord);
    return lastWord;
  }

  // For contenteditable elements (Gmail, rich text editors)
  if (element.isContentEditable) {
    try {
      const selection = window.getSelection();
      if (!selection.rangeCount) {
        debugLog("AutoText Debug: No selection range in contenteditable");
        return "";
      }

      const range = selection.getRangeAt(0);

      // For Gmail and complex contenteditable, we need to find the actual editable ancestor
      let editableElement = element;
      let node = range.startContainer;

      // Walk up to find the contenteditable element
      while (node && node !== document.body) {
        if (node.isContentEditable && node.nodeType === 1) {
          editableElement = node;
          break;
        }
        node = node.parentNode;
      }

      const preCaretRange = range.cloneRange();
      preCaretRange.selectNodeContents(editableElement);
      preCaretRange.setEnd(range.endContainer, range.endOffset);

      // Optimization: Only get the last 100 characters to avoid performance issues in large docs
      // We can't easily slice a Range, but we can try to limit the start
      // If the text is huge, toString() is expensive.
      // A better approach for huge text is to only look at the immediate text node if possible,
      // but that might miss cross-node words.
      // For now, let's just grab the text. If it's too slow, we'll need a more complex walker.
      let textBefore = preCaretRange.toString();

      // Optimization: Truncate if too long (we only need the last word)
      if (textBefore.length > 100) {
        textBefore = textBefore.slice(-100);
      }

      debugLog("AutoText Debug: contenteditable text before:", textBefore);

      // Extract the last word
      const match = textBefore.match(/(\S+)$/);
      let lastWord = match ? match[1] : "";

      // Clean zero-width characters and invisible Unicode characters
      lastWord = lastWord.replace(/[\u200B-\u200D\uFEFF]/g, '');

      debugLog("AutoText Debug: Extracted last word from contenteditable:", lastWord);
      return lastWord;
    } catch (error) {
      console.error("AutoText: Error getting text in contenteditable:", error);
      return "";
    }
  }

  return "";
}

// Replace text in input/textarea
function replaceInTextInput(element, shortcutKey, expansion) {
  const cursorPos = element.selectionStart;
  const textBefore = element.value.substring(0, cursorPos);
  const textAfter = element.value.substring(cursorPos);

  // Remove the shortcut key and add expansion
  const newTextBefore = textBefore.slice(0, -shortcutKey.length) + expansion;

  element.value = newTextBefore + textAfter;

  // Set cursor position after the expansion
  const newCursorPos = newTextBefore.length;
  element.selectionStart = element.selectionEnd = newCursorPos;

  // Trigger input event for frameworks (React, Vue, etc.)
  element.dispatchEvent(new Event('input', { bubbles: true }));
}

// Replace text in contenteditable (Gmail, rich text editors)
function replaceInContentEditable(element, shortcutKey, expansion, htmlExpansion) {
  try {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;

    const range = selection.getRangeAt(0);

    // Delete the shortcut key
    range.setStart(range.endContainer, range.endOffset - shortcutKey.length);
    range.deleteContents();

    // Insert the expansion (HTML if available, otherwise plain text)
    if (htmlExpansion) {
      // Create a document fragment from HTML
      const template = document.createElement('template');
      template.innerHTML = htmlExpansion;
      const fragment = template.content;

      range.insertNode(fragment);

      // Move cursor to end of inserted content
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      // Insert plain text
      const textNode = document.createTextNode(expansion);
      range.insertNode(textNode);

      // Move cursor after inserted text
      range.setStartAfter(textNode);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
    }

    // Trigger input event for the editor
    element.dispatchEvent(new Event('input', { bubbles: true }));
  } catch (error) {
    console.error("AutoText: Error replacing in contenteditable:", error);
  }
}

// Main handler for trigger key press
function handleTriggerKey(event) {
  // Check if AutoText is globally disabled (via keyboard shortcut toggle)
  if (!autotextEnabled) {
    return;
  }

  // Check if current site is blacklisted
  if (isBlacklisted()) {
    return;
  }

  // Check for configured trigger key (default: Tab)
  const triggerKey = settings.triggerKey || 'Tab';
  if (event.key !== triggerKey) {
    return;
  }

  let element = event.target;

  // Check if element is inside a contenteditable (for Gmail and complex editors)
  let isInContentEditable = false;
  let contentEditableParent = null;
  let node = element;

  while (node && node !== document.body) {
    if (node.isContentEditable && node.nodeType === 1) {
      isInContentEditable = true;
      contentEditableParent = node;
      break;
    }
    node = node.parentNode;
  }

  // Only process in text input elements or contenteditable
  if (
    element.tagName !== "INPUT" &&
    element.tagName !== "TEXTAREA" &&
    !isInContentEditable
  ) {
    return;
  }

  // If inside contenteditable, use the contenteditable parent as the element
  if (isInContentEditable && contentEditableParent) {
    element = contentEditableParent;
  }

  // Debug logging
  debugLog("AutoText Debug: Tab pressed", {
    elementType: element.tagName || 'contenteditable',
    isContentEditable: element.isContentEditable,
    cursorPos: element.selectionStart,
  });

  // Get the text before cursor
  const textBefore = getTextBeforeCursor(element);

  debugLog("AutoText Debug: Text before cursor:", {
    textBefore,
    length: textBefore.length,
    hasShortcut: !!shortcuts[textBefore]
  });

  if (!textBefore) {
    debugLog("AutoText Debug: No text before cursor, skipping");
    return;
  }

  // Check if it matches a shortcut
  const shortcut = shortcuts[textBefore];

  if (!shortcut) {
    debugLog("AutoText Debug: No shortcut found for:", textBefore);
    return;
  }

  debugLog("AutoText Debug: Shortcut match found!", textBefore);

  // We found a match! Prevent default Tab behavior
  event.preventDefault();
  event.stopPropagation();

  // Determine what content to use
  let textContent = shortcut.value;
  let htmlContent = shortcut.html_value;

  // If text is empty but HTML exists, extract text from HTML
  if (!textContent && htmlContent) {
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlContent;
    textContent = tempDiv.textContent || tempDiv.innerText || '';
  }

  debugLog(`AutoText: Expanding "${textBefore}" -> "${textContent || htmlContent}"`);

  // Replace based on element type
  if (element.tagName === "INPUT" || element.tagName === "TEXTAREA") {
    // For input/textarea, use plain text (extracted from HTML if needed)
    replaceInTextInput(element, textBefore, textContent);
  } else if (element.isContentEditable) {
    // For contenteditable, use HTML if available
    replaceInContentEditable(
      element,
      textBefore,
      textContent,
      htmlContent
    );
  }

  // Visual feedback
  showToast(textBefore, textContent || 'Rich text content');
  playExpansionSound();

  // Track usage statistics
  trackShortcutUsage(textBefore, shortcut.id);
}

// Listen for trigger key press
document.addEventListener("keydown", handleTriggerKey, true);

// Listen for settings changes
chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local") {
    if (changes.settings) {
      settings = { ...settings, ...changes.settings.newValue };
      debugLog("AutoText: Settings updated");
    }
    // Listen for global enabled/disabled toggle (from keyboard shortcut)
    if (changes.autotext_enabled !== undefined) {
      autotextEnabled = changes.autotext_enabled.newValue !== false;
      debugLog("AutoText: Extension", autotextEnabled ? "enabled" : "disabled");
    }
  }
});

// Initialize: load shortcuts and settings, inject styles
async function initialize() {
  await loadSettings();
  await loadShortcuts();
  injectFeedbackStyles();
  debugLog("AutoText: Content script loaded and ready");
}

initialize();
