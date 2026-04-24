// AutoText Content Script - Core text expansion logic
// Listens for Tab key, detects shortcuts, and replaces with expansions

const DEBUG = true; // TEMP: Enable to debug contenteditable issues
const debugLog = (...args) => {
  if (DEBUG) {
    console.log(...args);
  }
};

let shortcuts = {};
let autotextEnabled = true;  // Global toggle state
let settings = {
  triggerKey: 'Tab',
  triggerMode: 'key',   // 'key' (Tab/configured key) | 'space' (auto-expand on Space/Enter)
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
    const result = await chrome.storage.local.get(['auth_token', 'api_url']);

    // SECURITY: Skip if not properly configured
    // Never fall back to localhost - this would send data to whatever
    // service is running on the user's local machine (potential data leak)
    if (!result.auth_token || !result.api_url) {
      debugLog("AutoText: Skipping usage tracking - not configured");
      return;
    }

    // Fire-and-forget: don't await response to avoid blocking
    fetch(`${result.api_url}/track-usage/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${result.auth_token}`
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

// Sanitize HTML before inserting into DOM. Server-side bleach is not enough:
// once HTML hits the browser, mutation-XSS vectors (SVG foreignObject,
// noscript tricks) can surface. DOMPurify handles the client-side layer.
// We bundle lib/dompurify.min.js as a content script loaded before this one.
function safeHTML(dirty) {
  if (typeof DOMPurify !== 'undefined' && DOMPurify.sanitize) {
    return DOMPurify.sanitize(dirty, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ['style', 'script'],
      FORBID_ATTR: ['onerror', 'onload', 'onclick']
    });
  }
  // DOMPurify not loaded — refuse HTML entirely rather than risk XSS.
  // Caller should fall back to textContent path.
  console.warn('AutoText: DOMPurify unavailable, refusing HTML insert');
  return '';
}

// Set input/textarea value via the prototype's native setter so React's
// internal value tracker ("_valueTracker") sees the mutation. Without this,
// React re-renders using the last tracked value and overwrites our expansion
// on SPAs like Linear, Notion, Jira, Slack web, Facebook.
// See React issue #11488 and #10135 for the canonical pattern.
function setNativeValue(element, value) {
  const proto = element.tagName === 'TEXTAREA'
    ? HTMLTextAreaElement.prototype
    : HTMLInputElement.prototype;
  const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
  const setter = descriptor && descriptor.set;
  if (setter) {
    setter.call(element, value);
  } else {
    element.value = value;
  }
}

// ----------------------------------------------------------------------------
// Dynamic macros — evaluated at expansion time, before cursor marker handling.
// Supported syntax:
//   [[date]]                       → today, ISO short (DD.MM.YYYY)
//   [[date:short|medium|long]]     → localized format
//   [[date:DD.MM.YYYY]]            → custom tokens: YYYY MM DD HH mm
//   [[date+7d]], [[date-30d]]       → offset by days (d), weeks (w), months (m), years (y)
//   [[date+7d:DD.MM.YYYY]]          → offset + format combined
//   [[time]]                        → HH:mm
// Unknown tokens are preserved so snippets don't silently mangle content.
// ----------------------------------------------------------------------------
const DATE_MACRO_RE = /\[\[(date|time)(?:([+-])(\d+)([dwmy]))?(?::([^\]]+))?\]\]/g;

function _applyOffset(date, sign, amount, unit) {
  const mult = sign === '-' ? -1 : 1;
  const n = amount * mult;
  const d = new Date(date.getTime());
  switch (unit) {
    case 'd': d.setDate(d.getDate() + n); break;
    case 'w': d.setDate(d.getDate() + n * 7); break;
    case 'm': d.setMonth(d.getMonth() + n); break;
    case 'y': d.setFullYear(d.getFullYear() + n); break;
  }
  return d;
}

function _pad(n) {
  return String(n).padStart(2, '0');
}

function _formatDate(date, format) {
  // Custom token replacement (avoid overlapping matches via single pass)
  if (format && /YYYY|MM|DD|HH|mm/.test(format)) {
    return format
      .replace(/YYYY/g, date.getFullYear())
      .replace(/MM/g, _pad(date.getMonth() + 1))
      .replace(/DD/g, _pad(date.getDate()))
      .replace(/HH/g, _pad(date.getHours()))
      .replace(/mm/g, _pad(date.getMinutes()));
  }
  // Intl preset (short/medium/long/full) — explicit names only
  if (['short', 'medium', 'long', 'full'].includes(format)) {
    return new Intl.DateTimeFormat(undefined, { dateStyle: format }).format(date);
  }
  // Default: DD.MM.YYYY (Romanian/European-friendly, deterministic)
  return `${_pad(date.getDate())}.${_pad(date.getMonth() + 1)}.${date.getFullYear()}`;
}

function processDateMacros(input, now = new Date()) {
  if (!input || typeof input !== 'string') return input;
  return input.replace(DATE_MACRO_RE, (match, kind, sign, amount, unit, format) => {
    try {
      const target = (sign && amount && unit)
        ? _applyOffset(now, sign, parseInt(amount, 10), unit)
        : now;
      if (kind === 'time') {
        return format
          ? _formatDate(target, format)
          : `${_pad(target.getHours())}:${_pad(target.getMinutes())}`;
      }
      return _formatDate(target, format);
    } catch (e) {
      console.warn('AutoText: date macro error for', match, e);
      return match;
    }
  });
}

// Extract cursor marker position from expansion. Returns {text, cursorOffset}
// where cursorOffset is the index in `text` where the caret should land,
// or null if no marker. Marker is literal "$|$" — picked because it's
// unlikely in natural user content and keeps snippets copy-pasteable.
const CURSOR_MARKER = '$|$';
function extractCursorMarker(expansion) {
  const idx = expansion.indexOf(CURSOR_MARKER);
  if (idx === -1) return { text: expansion, cursorOffset: null };
  return {
    text: expansion.slice(0, idx) + expansion.slice(idx + CURSOR_MARKER.length),
    cursorOffset: idx,
  };
}

// Replace text in input/textarea
function replaceInTextInput(element, shortcutKey, expansion) {
  const cursorPos = element.selectionStart;
  const textBefore = element.value.substring(0, cursorPos);
  const textAfter = element.value.substring(cursorPos);

  // Resolve cursor marker (if any) before splicing
  const { text: expansionText, cursorOffset } = extractCursorMarker(expansion);

  // Remove the shortcut key and add expansion
  const newTextBefore = textBefore.slice(0, -shortcutKey.length) + expansionText;

  setNativeValue(element, newTextBefore + textAfter);

  // Cursor lands at marker if present, otherwise at end of expansion
  const base = newTextBefore.length - expansionText.length;
  const newCursorPos = cursorOffset !== null
    ? base + cursorOffset
    : newTextBefore.length;
  element.selectionStart = element.selectionEnd = newCursorPos;

  // Trigger input event for frameworks (React, Vue, etc.)
  element.dispatchEvent(new Event('input', { bubbles: true }));
}

// Detect modern rich-text editor frameworks whose internal state must be
// notified via beforeinput/input events. For these, Range.deleteContents
// + insertNode leaves the framework's internal doc model untouched and the
// next render overwrites our insertion. execCommand('insertText') is formally
// deprecated but remains the only reliable path for ProseMirror / Lexical
// / Slate-based editors (Notion, modern Slack, Reddit composer, etc.).
function detectEditorFramework(element) {
  // Walk up to document root looking for framework markers
  let node = element;
  while (node && node.nodeType === 1) {
    if (node.classList && node.classList.contains('ProseMirror')) return 'prosemirror';
    if (node.dataset && node.dataset.lexicalEditor === 'true') return 'lexical';
    if (node.dataset && node.dataset.slateEditor === 'true') return 'slate';
    node = node.parentNode;
  }
  return null;
}

// Replace text in contenteditable (Gmail, rich text editors)
function replaceInContentEditable(element, shortcutKey, expansion, htmlExpansion) {
  try {
    const selection = window.getSelection();
    if (!selection.rangeCount) return;

    // Framework-aware fast path: ProseMirror / Lexical / Slate intercept
    // beforeinput events and update their own model. Plain Range manipulation
    // is ignored and reverted on next render. execCommand('insertText') feeds
    // the framework its expected signal.
    const framework = detectEditorFramework(element);
    if (framework && !htmlExpansion) {
      const range = selection.getRangeAt(0);
      range.setStart(range.endContainer, range.endOffset - shortcutKey.length);
      selection.removeAllRanges();
      selection.addRange(range);

      const { text: frameworkText, cursorOffset } = extractCursorMarker(expansion);
      // execCommand is sync; returns false if not supported in this context.
      if (document.execCommand && document.execCommand('insertText', false, frameworkText)) {
        // Position caret at marker if present
        if (cursorOffset !== null) {
          const backSteps = frameworkText.length - cursorOffset;
          for (let i = 0; i < backSteps; i++) {
            selection.modify('move', 'backward', 'character');
          }
        }
        debugLog(`AutoText: framework=${framework}, used execCommand insertText`);
        return;
      }
      debugLog(`AutoText: framework=${framework}, execCommand refused, fallback`);
    }

    const range = selection.getRangeAt(0);

    // Delete the shortcut key
    range.setStart(range.endContainer, range.endOffset - shortcutKey.length);
    range.deleteContents();

    // Insert the expansion (HTML if available, otherwise plain text).
    // Use Range.createContextualFragment — parses HTML in the caret's node
    // context. Combined with DOMPurify upstream, this is the safest pattern
    // (no direct innerHTML assignment).
    if (htmlExpansion) {
      const clean = safeHTML(htmlExpansion);
      const fragment = range.createContextualFragment(clean);

      range.insertNode(fragment);

      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      // Insert plain text — convert newlines to <br> for contenteditable.
      // Escape angle brackets first; DOMPurify re-sanitizes defensively.
      if (expansion.includes('\n')) {
        const escaped = expansion
          .split('\n')
          .map(line => line.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
          .join('<br>');
        const clean = safeHTML(escaped);
        const fragment = range.createContextualFragment(clean);

        range.insertNode(fragment);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
      } else {
        // Single line - use text node with cursor marker support
        const { text: plainText, cursorOffset } = extractCursorMarker(expansion);
        const textNode = document.createTextNode(plainText);
        range.insertNode(textNode);

        if (cursorOffset !== null) {
          // Land caret at marker position within the inserted text node
          range.setStart(textNode, cursorOffset);
          range.collapse(true);
        } else {
          range.setStartAfter(textNode);
          range.collapse(true);
        }
        selection.removeAllRanges();
        selection.addRange(range);
      }
    }

    // Trigger input event for the editor
    element.dispatchEvent(new Event('input', { bubbles: true }));
  } catch (error) {
    console.error("AutoText: Error replacing in contenteditable:", error);
  }
}

// Main handler for trigger key press
// Returns true when the Tab key on Gmail's To:/Cc:/Bcc:/Subject: fields
// should stay with Gmail for field navigation. Intercepting Tab there
// breaks keyboard nav — reported repeatedly on similar extensions
// (ProKeys issue thread). Gmail compose body is NOT affected.
function isGmailFormNavigation(element, triggerKey) {
  if (triggerKey !== 'Tab') return false;
  if (window.location.hostname !== 'mail.google.com') return false;
  if (!element || !element.closest) return false;
  // Gmail recipient / subject inputs live inside a <form> as plain inputs.
  // Body composer is contenteditable (div), no enclosing <form>.
  const form = element.closest('form');
  if (!form) return false;
  const tag = element.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA';
}

// Determine whether `event.key` is the configured trigger in the current mode.
// 'key' mode: one specific key (Tab by default).
// 'space' mode: auto-expand when user finishes a word — Space or Enter.
function isTriggerKey(event, currentSettings) {
  const mode = currentSettings.triggerMode || 'key';
  if (mode === 'space') {
    return event.key === ' ' || event.key === 'Enter';
  }
  return event.key === (currentSettings.triggerKey || 'Tab');
}

function handleTriggerKey(event) {
  // Check if AutoText is globally disabled (via keyboard shortcut toggle)
  if (!autotextEnabled) {
    return;
  }

  // Check if current site is blacklisted
  if (isBlacklisted()) {
    return;
  }

  // Respect configured trigger: Tab (default), custom key, or Space/Enter mode.
  if (!isTriggerKey(event, settings)) {
    return;
  }
  const triggerKey = event.key;
  const isSpaceMode = (settings.triggerMode || 'key') === 'space';

  let element = event.target;

  // Gmail form navigation takes priority over expansion on To:/Subject:
  if (isGmailFormNavigation(element, triggerKey)) {
    debugLog('AutoText: Gmail form Tab — yielding to native navigation');
    return;
  }

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

  // In 'key' mode (Tab), prevent focus change. In 'space' mode, let Space/
  // Enter type naturally after expansion — that's the natural UX (word ends
  // with the space/newline user just pressed).
  if (!isSpaceMode) {
    event.preventDefault();
    event.stopPropagation();
  }

  // Determine what content to use
  let textContent = shortcut.value;
  let htmlContent = shortcut.html_value;

  // If text is empty but HTML exists, extract text from HTML without
  // touching innerHTML (mutation-XSS surface). DOMParser gives a detached
  // document whose textContent is safe to read.
  if (!textContent && htmlContent) {
    const doc = new DOMParser().parseFromString(htmlContent, 'text/html');
    textContent = (doc.body && doc.body.textContent) || '';
  }

  // Resolve dynamic macros ([[date]], [[date+7d]], etc.) before insert.
  // Run on both text and HTML paths so snippets authored either way work.
  textContent = processDateMacros(textContent);
  if (htmlContent) {
    htmlContent = processDateMacros(htmlContent);
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

// Initialize: load shortcuts and settings, inject styles
async function initialize() {
  await loadSettings();
  await loadShortcuts();
  injectFeedbackStyles();
  debugLog("AutoText: Content script loaded and ready");
}

// Node (Jest) exposure — side effects wrapped so tests don't trigger listeners
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    isBlacklisted,
    getTextBeforeCursor,
    replaceInTextInput,
    replaceInContentEditable,
    setNativeValue,
    detectEditorFramework,
    safeHTML,
    isGmailFormNavigation,
    extractCursorMarker,
    processDateMacros,
    isTriggerKey,
    loadSettings,
    // Allow tests to mutate module state via setters
    _getSettings: () => settings,
    _setSettings: (next) => { settings = { ...settings, ...next }; },
    _setShortcuts: (next) => { shortcuts = next; },
    _setEnabled: (v) => { autotextEnabled = v; },
  };
} else {
  // Browser content script — attach listeners and boot
  document.addEventListener("keydown", handleTriggerKey, true);

  chrome.storage.onChanged.addListener((changes, areaName) => {
    if (areaName === "local") {
      if (changes.settings) {
        settings = { ...settings, ...changes.settings.newValue };
        debugLog("AutoText: Settings updated");
      }
      if (changes.autotext_enabled !== undefined) {
        autotextEnabled = changes.autotext_enabled.newValue !== false;
        debugLog("AutoText: Extension", autotextEnabled ? "enabled" : "disabled");
      }
    }
  });

  initialize();
}
