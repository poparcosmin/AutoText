/**
 * Tests for content.js — text expansion logic.
 *
 * Covers: blacklist, cursor-based extraction, text replacement in input/textarea
 * and contenteditable. Uses jsdom (via jest-environment-jsdom).
 */

require('./setup');

const content = require('../content');

describe('content.js — text expansion core', () => {
  beforeEach(() => {
    // Reset module state between tests
    content._setSettings({ blacklistedSites: [] });
    content._setShortcuts({});
    content._setEnabled(true);
  });

  // ---------------------------------------------------------------------------
  describe('isBlacklisted()', () => {
    it('returns false when blacklist is empty', () => {
      content._setSettings({ blacklistedSites: [] });
      expect(content.isBlacklisted()).toBe(false);
    });

    it('returns true when current hostname matches a blacklist entry', () => {
      // jsdom default hostname is "localhost"
      content._setSettings({ blacklistedSites: ['localhost'] });
      expect(content.isBlacklisted()).toBe(true);
    });

    it('returns true for partial hostname match (substring)', () => {
      content._setSettings({ blacklistedSites: ['local'] });
      expect(content.isBlacklisted()).toBe(true);
    });

    it('returns false for unrelated hostnames', () => {
      content._setSettings({ blacklistedSites: ['example.com', 'mail.google.com'] });
      expect(content.isBlacklisted()).toBe(false);
    });
  });

  // ---------------------------------------------------------------------------
  describe('getTextBeforeCursor() on input/textarea', () => {
    it('extracts the last word before the cursor in an <input>', () => {
      const input = document.createElement('input');
      input.value = 'hello //sig';
      document.body.appendChild(input);
      input.setSelectionRange(input.value.length, input.value.length);

      expect(content.getTextBeforeCursor(input)).toBe('//sig');
    });

    it('extracts the last word before the cursor in a <textarea>', () => {
      const ta = document.createElement('textarea');
      ta.value = 'line one\nline //two';
      document.body.appendChild(ta);
      ta.setSelectionRange(ta.value.length, ta.value.length);

      expect(content.getTextBeforeCursor(ta)).toBe('//two');
    });

    it('returns empty string when cursor is at the very start', () => {
      const input = document.createElement('input');
      input.value = 'abc';
      document.body.appendChild(input);
      input.setSelectionRange(0, 0);

      expect(content.getTextBeforeCursor(input)).toBe('');
    });

    it('strips zero-width / invisible Unicode characters', () => {
      const zws = String.fromCharCode(0x200B);
      const input = document.createElement('input');
      input.value = '//sig' + zws;
      document.body.appendChild(input);
      input.setSelectionRange(input.value.length, input.value.length);

      expect(content.getTextBeforeCursor(input)).toBe('//sig');
    });

    it('returns empty string for non-text elements', () => {
      const div = document.createElement('div');
      document.body.appendChild(div);
      expect(content.getTextBeforeCursor(div)).toBe('');
    });
  });

  // ---------------------------------------------------------------------------
  describe('replaceInTextInput()', () => {
    it('replaces the shortcut key with the expansion text', () => {
      const input = document.createElement('input');
      input.value = 'hello //sig';
      document.body.appendChild(input);
      input.setSelectionRange(input.value.length, input.value.length);

      content.replaceInTextInput(input, '//sig', 'Cosmin Popa');

      expect(input.value).toBe('hello Cosmin Popa');
    });

    it('moves the cursor to end of expansion', () => {
      const input = document.createElement('input');
      input.value = '//sig plus tail';
      document.body.appendChild(input);
      // cursor right after "//sig"
      input.setSelectionRange(5, 5);

      content.replaceInTextInput(input, '//sig', 'Cosmin');

      expect(input.selectionStart).toBe('Cosmin'.length);
      expect(input.selectionEnd).toBe('Cosmin'.length);
      expect(input.value).toBe('Cosmin plus tail');
    });

    it('dispatches an input event so React/Vue listeners update', () => {
      const input = document.createElement('input');
      input.value = '//sig';
      document.body.appendChild(input);
      input.setSelectionRange(input.value.length, input.value.length);

      const listener = jest.fn();
      input.addEventListener('input', listener);

      content.replaceInTextInput(input, '//sig', 'X');

      expect(listener).toHaveBeenCalledTimes(1);
      // Event should bubble
      expect(listener.mock.calls[0][0].bubbles).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  describe('replaceInContentEditable()', () => {
    it('inserts plain-text expansion and removes the shortcut key', () => {
      const editable = document.createElement('div');
      editable.setAttribute('contenteditable', 'true');
      const textNode = document.createTextNode('hello //sig');
      editable.appendChild(textNode);
      document.body.appendChild(editable);

      // Place caret at end of the text node (required for jsdom Range.deleteContents)
      const range = document.createRange();
      range.setStart(textNode, textNode.length);
      range.setEnd(textNode, textNode.length);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);

      content.replaceInContentEditable(editable, '//sig', 'Cosmin Popa', null);

      expect(editable.textContent).not.toContain('//sig');
      expect(editable.textContent).toContain('Cosmin');
    });

    it('returns early when there is no selection range (no crash)', () => {
      const editable = document.createElement('div');
      editable.setAttribute('contenteditable', 'true');
      document.body.appendChild(editable);

      window.getSelection().removeAllRanges();

      // Should not throw
      expect(() => {
        content.replaceInContentEditable(editable, '//sig', 'Cosmin', null);
      }).not.toThrow();
    });
  });

  // ---------------------------------------------------------------------------
  describe('loadSettings()', () => {
    it('merges stored settings into current settings', async () => {
      chrome.storage.local._data.settings = {
        blacklistedSites: ['foo.com'],
        playSound: true,
      };
      chrome.storage.local._data.autotext_enabled = true;

      await content.loadSettings();

      const merged = content._getSettings();
      expect(merged.blacklistedSites).toEqual(['foo.com']);
      expect(merged.playSound).toBe(true);
      // Pre-existing defaults preserved
      expect(merged.triggerKey).toBe('Tab');
    });

    it('does not crash when storage is empty', async () => {
      chrome.storage.local._data = {};
      await expect(content.loadSettings()).resolves.toBeUndefined();
    });
  });
});
