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

// ----------------------------------------------------------------------------
// Form placeholders — {{name}}, {{name:Label}}, {{name:Label|default}}
// At expansion time each unique placeholder prompts for a value. Answers
// substitute all occurrences of the same name in the snippet. Cancel aborts
// the entire expansion (returns null; caller leaves shortcut text intact).
// Note: uses native prompt() — minimal UX. A proper inline popup with
// shadow-DOM CSS isolation is tracked as a separate follow-up.
// ----------------------------------------------------------------------------
const PLACEHOLDER_RE = /\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([^|}]*))?(?:\|([^}]*))?\}\}/g;

function extractPlaceholders(input) {
  if (!input || typeof input !== 'string') return [];
  const seen = new Set();
  const fields = [];
  let m;
  PLACEHOLDER_RE.lastIndex = 0;
  while ((m = PLACEHOLDER_RE.exec(input)) !== null) {
    const [, name, label, def] = m;
    if (seen.has(name)) continue;
    seen.add(name);
    fields.push({ name, label: (label || name).trim(), default: (def || '').trim() });
  }
  return fields;
}

function substitutePlaceholders(input, values) {
  return input.replace(PLACEHOLDER_RE, (_match, name) => {
    return Object.prototype.hasOwnProperty.call(values, name) ? values[name] : '';
  });
}

// Ask the user for each placeholder value via native prompt().
// Returns {values: {...}} on success, {cancelled: true} if user cancels any.
function promptForPlaceholders(fields, askFn) {
  const ask = askFn || ((label, def) => window.prompt(label, def));
  const values = {};
  for (const f of fields) {
    const answer = ask(f.label, f.default);
    if (answer === null) return { cancelled: true };
    values[f.name] = answer;
  }
  return { values };
}

// ----------------------------------------------------------------------------
// Snippet nesting — [[%s(otherShortcut)]] expands another snippet inline.
// Allows composition: "email-footer" used inside 20 templates, update once.
// Safety: depth cap of 5 + visited set catch infinite recursion.
// ----------------------------------------------------------------------------
const NESTING_RE = /\[\[%s\(([^)]+)\)\]\]/g;
const MAX_NESTING_DEPTH = 5;

function processSnippetNesting(input, shortcutsMap, depth = 0, visited = new Set()) {
  if (!input || typeof input !== 'string') return input;
  if (depth >= MAX_NESTING_DEPTH) {
    console.warn(`AutoText: nesting depth ${MAX_NESTING_DEPTH} exceeded, stopping`);
    return input;
  }
  return input.replace(NESTING_RE, (match, name) => {
    const trimmed = name.trim();
    if (visited.has(trimmed)) {
      console.warn(`AutoText: nesting cycle detected on "${trimmed}"`);
      return `[cycle:${trimmed}]`;
    }
    const nested = shortcutsMap && shortcutsMap[trimmed];
    if (!nested) {
      return `[missing:${trimmed}]`;
    }
    const body = nested.value || nested.html_value || '';
    // Recursive expand — add this name to visited so we catch self-reference
    const nextVisited = new Set(visited);
    nextVisited.add(trimmed);
    return processSnippetNesting(body, shortcutsMap, depth + 1, nextVisited);
  });
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

// ----------------------------------------------------------------------------
// System variables — [[day]], [[greeting]], [[user]], [[clipboard]],
// [[random:A|B|C]]. Reuses [[...]] convention to stay consistent with date
// macros and snippet nesting. Async because clipboard + user reads cross
// the chrome.storage / clipboard boundaries; date macros remain sync since
// they are pure computation on `new Date()`.
//
// Pipeline ordering (vezi handleTriggerKey): nesting -> date -> system ->
// placeholders -> cursor. System vars run after date so [[date]] is resolved
// first (defensive — current grammars don't overlap, but ordering is cheap
// insurance for future additions).
// ----------------------------------------------------------------------------
const SYSTEM_VAR_RE = /\[\[(day|greeting|user|clipboard|random)(?::([^\]]*))?\]\]/g;

const ROMANIAN_DAY_NAMES = [
  'Duminica', 'Luni', 'Marti', 'Miercuri', 'Joi', 'Vineri', 'Sambata'
];

function _greeting(date) {
  const h = date.getHours();
  if (h < 11) return 'Buna dimineata';
  if (h < 18) return 'Buna ziua';
  return 'Buna seara';
}

function _randomPick(args) {
  if (!args) return '';
  const options = args.split('|').map(s => s.trim()).filter(Boolean);
  if (options.length === 0) return '';
  return options[Math.floor(Math.random() * options.length)];
}

async function _readUsername() {
  try {
    const stored = await chrome.storage.local.get('username');
    return (stored && stored.username) || '';
  } catch {
    return '';
  }
}

async function _readClipboard() {
  try {
    const text = await navigator.clipboard.readText();
    return text || '';
  } catch (err) {
    // Permission denied or not in user-gesture context.
    // showToast is defined later in the file; guard at call site.
    if (typeof showToast === 'function') {
      showToast('clipboard', 'Permite acces la clipboard din chrome://settings');
    }
    return '';
  }
}

// Find all matches via matchAll, resolve async ones in parallel, then
// reassemble via index-based slicing. Avoids reentrancy bug where
// String.replace would re-scan replacement text — if a future resolver
// returns text containing `[[...]]`, we must NOT process it again.
async function processSystemVars(input, now = new Date()) {
  if (!input || typeof input !== 'string') return input;
  const matches = [...input.matchAll(SYSTEM_VAR_RE)];
  if (matches.length === 0) return input;

  const replacements = await Promise.all(matches.map(async (m) => {
    const kind = m[1];
    const args = m[2];
    try {
      switch (kind) {
        case 'day': return ROMANIAN_DAY_NAMES[now.getDay()];
        case 'greeting': return _greeting(now);
        case 'random': return _randomPick(args || '');
        case 'user': return await _readUsername();
        case 'clipboard': return await _readClipboard();
        default: return '';
      }
    } catch (err) {
      console.warn('AutoText: system var', kind, 'failed:', err);
      return '';
    }
  }));

  const out = [];
  let lastIdx = 0;
  matches.forEach((m, i) => {
    out.push(input.slice(lastIdx, m.index));
    out.push(replacements[i]);
    lastIdx = m.index + m[0].length;
  });
  out.push(input.slice(lastIdx));
  return out.join('');
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

async function handleTriggerKey(event) {
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

  // Expansion pipeline (ordering matters):
  //   1. Snippet nesting — flatten [[%s(other)]] references recursively
  //   2. Date macros — [[date]], [[date+7d]], etc.
  //   3. System vars — [[day]], [[greeting]], [[user]], [[clipboard]], [[random:A|B|C]]
  //   4. Form placeholders — {{name:Label|default}}, prompted interactively
  // Cursor marker ($|$) is handled later, inside replace* functions.
  textContent = processSnippetNesting(textContent, shortcuts);
  if (htmlContent) {
    htmlContent = processSnippetNesting(htmlContent, shortcuts);
  }
  textContent = processDateMacros(textContent);
  if (htmlContent) {
    htmlContent = processDateMacros(htmlContent);
  }
  textContent = await processSystemVars(textContent);
  if (htmlContent) {
    htmlContent = await processSystemVars(htmlContent);
  }

  // Collect placeholders across both text and html (same field fills both).
  const fields = extractPlaceholders((textContent || '') + '\n' + (htmlContent || ''));
  if (fields.length > 0) {
    const result = promptForPlaceholders(fields);
    if (result.cancelled) {
      debugLog('AutoText: placeholder fill cancelled, aborting expansion');
      return;
    }
    textContent = substitutePlaceholders(textContent, result.values);
    if (htmlContent) {
      htmlContent = substitutePlaceholders(htmlContent, result.values);
    }
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

// ----------------------------------------------------------------------------
// Command palette — inline overlay, Alt+Shift+P to open.
// Substring-match search across shortcut keys and values; Enter inserts the
// matched expansion at the saved focus target.
// Shadow DOM wraps the overlay so page CSS doesn't bleed into our UI.
// ----------------------------------------------------------------------------
let paletteState = null;  // { host, shadow, input, list, savedTarget, savedRange }

// Subsequence fuzzy scorer — every char of `needle` must appear in order in
// `haystack`, but not necessarily contiguous. Earlier matches score higher
// (1/(idx+1)); chars closer together compound. Returns 0 when no match,
// otherwise a small positive number. Threshold of 0.1 is permissive — when
// a query already failed substring tests, we'd rather over-include than miss.
function fuzzyScore(needle, haystack) {
  if (!needle || !haystack) return 0;
  let hayIdx = 0;
  let score = 0;
  for (const ch of needle) {
    const found = haystack.indexOf(ch, hayIdx);
    if (found === -1) return 0;
    score += 1 / (found - hayIdx + 1);
    hayIdx = found + 1;
  }
  return score;
}

function filterShortcuts(query, shortcutsMap) {
  const q = (query || '').toLowerCase().trim();
  const entries = Object.entries(shortcutsMap || {});
  if (!q) return entries.slice(0, 50).map(([key, s]) => ({ key, ...s }));
  const scored = [];
  for (const [key, s] of entries) {
    const keyL = key.toLowerCase();
    const valL = ((s.value || s.html_value) || '').toLowerCase();
    let score = 0;
    if (keyL === q) score = 100;
    else if (keyL.startsWith(q)) score = 80;
    else if (keyL.includes(q)) score = 60;
    else if (valL.includes(q)) score = 30;
    else {
      // Fuzzy fallback — give a few low-tier hits instead of nothing.
      // Multiplier keeps fuzzy hits below substring matches even at the
      // best possible fuzzy score (~5 for short query in short key).
      const fz = Math.max(fuzzyScore(q, keyL), fuzzyScore(q, valL) * 0.5);
      if (fz > 0.1) score = fz;
    }
    if (score > 0) scored.push({ key, score, ...s });
  }
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, 50);
}

function saveFocusTarget() {
  const active = document.activeElement;
  if (!active) return null;
  const isText = active.tagName === 'INPUT' || active.tagName === 'TEXTAREA';
  const isCE = active.isContentEditable;
  if (!isText && !isCE) return null;
  const saved = { target: active };
  if (isText) {
    saved.selectionStart = active.selectionStart;
    saved.selectionEnd = active.selectionEnd;
  } else {
    const sel = window.getSelection();
    saved.range = sel.rangeCount ? sel.getRangeAt(0).cloneRange() : null;
  }
  return saved;
}

function restoreFocusAndInsert(saved, expansion) {
  if (!saved || !saved.target) return;
  const el = saved.target;
  el.focus();
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
    const start = saved.selectionStart || 0;
    const before = el.value.substring(0, start);
    const after = el.value.substring(saved.selectionEnd || start);
    const { text: plainText, cursorOffset } = extractCursorMarker(expansion);
    setNativeValue(el, before + plainText + after);
    const newPos = cursorOffset !== null
      ? before.length + cursorOffset
      : before.length + plainText.length;
    el.selectionStart = el.selectionEnd = newPos;
    el.dispatchEvent(new Event('input', { bubbles: true }));
  } else if (el.isContentEditable && saved.range) {
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(saved.range);
    const { text: plainText, cursorOffset } = extractCursorMarker(expansion);
    const node = document.createTextNode(plainText);
    saved.range.insertNode(node);
    if (cursorOffset !== null) {
      saved.range.setStart(node, cursorOffset);
      saved.range.collapse(true);
    } else {
      saved.range.setStartAfter(node);
      saved.range.collapse(true);
    }
    sel.removeAllRanges();
    sel.addRange(saved.range);
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
}

function closeCommandPalette() {
  if (paletteState && paletteState.host && paletteState.host.parentNode) {
    paletteState.host.parentNode.removeChild(paletteState.host);
  }
  paletteState = null;
}

function renderPaletteList(query) {
  if (!paletteState) return;
  const results = filterShortcuts(query, shortcuts);
  const list = paletteState.list;
  while (list.firstChild) list.removeChild(list.firstChild);
  results.forEach((r, idx) => {
    const row = document.createElement('div');
    row.className = 'at-row' + (idx === 0 ? ' at-active' : '');
    row.dataset.shortcutKey = r.key;
    const k = document.createElement('span');
    k.className = 'at-key';
    k.textContent = r.key;
    const v = document.createElement('span');
    v.className = 'at-preview';
    const body = (r.value || r.html_value || '').slice(0, 60);
    v.textContent = body;
    row.appendChild(k);
    row.appendChild(v);
    row.addEventListener('click', () => selectPaletteRow(row));
    list.appendChild(row);
  });
  if (!results.length) {
    const empty = document.createElement('div');
    empty.className = 'at-empty';
    empty.textContent = query ? 'No matches' : 'No shortcuts yet — add some in Options';
    list.appendChild(empty);
  }
}

function moveActive(direction) {
  if (!paletteState) return;
  const rows = paletteState.list.querySelectorAll('.at-row');
  if (!rows.length) return;
  let idx = -1;
  rows.forEach((r, i) => { if (r.classList.contains('at-active')) idx = i; });
  rows.forEach(r => r.classList.remove('at-active'));
  const next = Math.max(0, Math.min(rows.length - 1, idx + direction));
  rows[next].classList.add('at-active');
  rows[next].scrollIntoView({ block: 'nearest' });
}

function selectPaletteRow(row) {
  if (!row || !paletteState) return;
  const key = row.dataset.shortcutKey;
  const s = shortcuts[key];
  if (!s) { closeCommandPalette(); return; }
  const expansion = s.value || s.html_value || '';
  const saved = paletteState.savedTarget;
  closeCommandPalette();
  if (saved) restoreFocusAndInsert(saved, expansion);
}

function confirmActivePalette() {
  if (!paletteState) return;
  const active = paletteState.list.querySelector('.at-row.at-active');
  if (active) selectPaletteRow(active);
}

function openCommandPalette() {
  if (paletteState) return;  // already open
  const savedTarget = saveFocusTarget();

  const host = document.createElement('div');
  host.id = 'autotext-palette-host';
  host.style.cssText =
    'position:fixed;inset:0;z-index:2147483647;pointer-events:none;';
  const shadow = host.attachShadow({ mode: 'closed' });

  // Inline styles — isolated from page CSS via shadow DOM.
  const style = document.createElement('style');
  style.textContent = `
    .at-backdrop { position:fixed;inset:0;background:rgba(0,0,0,0.35);pointer-events:auto; }
    .at-box { position:fixed;top:15vh;left:50%;transform:translateX(-50%);
      width:min(560px,90vw);background:#fff;color:#222;border-radius:10px;
      box-shadow:0 10px 40px rgba(0,0,0,0.3);font-family:-apple-system,BlinkMacSystemFont,
      "Segoe UI",sans-serif;overflow:hidden;pointer-events:auto; }
    .at-input { width:100%;border:none;outline:none;padding:16px 18px;font-size:16px;
      box-sizing:border-box;border-bottom:1px solid #eee; }
    .at-list { max-height:50vh;overflow-y:auto; }
    .at-row { display:flex;gap:12px;padding:10px 18px;cursor:pointer;align-items:center; }
    .at-row.at-active { background:#f0f4ff; }
    .at-row:hover { background:#f7f7f7; }
    .at-key { font-weight:600;color:#4CAF50;min-width:90px;font-family:monospace; }
    .at-preview { color:#666;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap; }
    .at-empty { padding:24px 18px;text-align:center;color:#999; }
    @media (prefers-color-scheme: dark) {
      .at-box { background:#1e1e1e;color:#eee; }
      .at-input { background:transparent;color:#eee;border-bottom-color:#333; }
      .at-row.at-active { background:#2a3550; }
      .at-row:hover { background:#2a2a2a; }
      .at-preview { color:#aaa; }
    }
  `;
  shadow.appendChild(style);

  const backdrop = document.createElement('div');
  backdrop.className = 'at-backdrop';
  backdrop.addEventListener('click', closeCommandPalette);
  shadow.appendChild(backdrop);

  const box = document.createElement('div');
  box.className = 'at-box';

  const input = document.createElement('input');
  input.className = 'at-input';
  input.type = 'text';
  input.placeholder = 'Search shortcuts...';
  input.spellcheck = false;
  box.appendChild(input);

  const list = document.createElement('div');
  list.className = 'at-list';
  box.appendChild(list);
  shadow.appendChild(box);
  document.documentElement.appendChild(host);

  paletteState = { host, shadow, input, list, savedTarget };

  input.addEventListener('input', () => renderPaletteList(input.value));
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { e.preventDefault(); closeCommandPalette(); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); moveActive(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); moveActive(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); confirmActivePalette(); }
  });

  renderPaletteList('');
  input.focus();
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
    processSystemVars,
    processSnippetNesting,
    extractPlaceholders,
    substitutePlaceholders,
    promptForPlaceholders,
    filterShortcuts,
    openCommandPalette,
    closeCommandPalette,
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

  // Command palette: opened via keyboard shortcut (Alt+Shift+P), routed from
  // background.js via chrome.tabs.sendMessage to the active tab.
  chrome.runtime.onMessage.addListener((req, sender, sendResponse) => {
    if (sender.id !== chrome.runtime.id) return false;
    if (req && req.action === 'openPalette') {
      openCommandPalette();
      sendResponse({ status: 'opened' });
      return true;
    }
    return false;
  });

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
