/**
 * Tests for content.js — text expansion logic.
 *
 * Covers: blacklist, cursor-based extraction, text replacement in input/textarea
 * and contenteditable. Uses jsdom (via jest-environment-jsdom).
 */

require('./setup');

// DOMPurify is loaded as a separate content script before content.js in prod.
// In Jest we need to globally expose it so safeHTML picks it up.
global.DOMPurify = require('dompurify');

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

    it('matches subdomain when parent domain is blocklisted', () => {
      // jsdom default hostname is "localhost" — use partial match behavior
      // Adding "local" to blocklist should match hostname "localhost"
      content._setSettings({ blacklistedSites: ['local'] });
      expect(content.isBlacklisted()).toBe(true);
    });

    it('blocklist entry list with whitespace trimmed (simulates save path)', () => {
      // options.js trims and filters empty lines before save; verify the
      // runtime side handles a clean list correctly.
      content._setSettings({ blacklistedSites: ['localhost', 'foo.com'] });
      expect(content.isBlacklisted()).toBe(true);
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

    it('writes through the HTMLInputElement prototype setter (React tracker path)', () => {
      // React patches the instance-level value setter to intercept writes.
      // Our fix must route through the prototype descriptor setter so
      // React's internal _valueTracker sees the change. This simulates
      // React's patched instance setter and verifies the prototype route.
      const input = document.createElement('input');
      input.value = '//sig';
      document.body.appendChild(input);
      input.setSelectionRange(input.value.length, input.value.length);

      const protoSetter = Object.getOwnPropertyDescriptor(
        HTMLInputElement.prototype, 'value'
      ).set;
      const protoSpy = jest.fn(function (v) { protoSetter.call(this, v); });
      Object.defineProperty(HTMLInputElement.prototype, 'value', {
        configurable: true,
        get: Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').get,
        set: protoSpy,
      });

      try {
        content.replaceInTextInput(input, '//sig', 'Popa');
        expect(protoSpy).toHaveBeenCalledWith('Popa');
        expect(input.value).toBe('Popa');
      } finally {
        Object.defineProperty(HTMLInputElement.prototype, 'value', {
          configurable: true,
          get: Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').get,
          set: protoSetter,
        });
      }
    });

    it('setNativeValue falls back to direct assignment when descriptor is missing', () => {
      const input = document.createElement('input');
      document.body.appendChild(input);

      content.setNativeValue(input, 'direct-assign');
      expect(input.value).toBe('direct-assign');
    });

    describe('safeHTML() — XSS guard', () => {
      it('strips <script> tags', () => {
        const hostile = '<p>hi</p><script>alert(1)</script>';
        const clean = content.safeHTML(hostile);
        expect(clean).toContain('<p>hi</p>');
        expect(clean).not.toContain('<script');
        expect(clean).not.toContain('alert(1)');
      });

      it('strips onerror inline handler', () => {
        const hostile = '<img src=x onerror="alert(1)">';
        const clean = content.safeHTML(hostile);
        expect(clean).not.toMatch(/onerror/i);
      });

      it('strips javascript: href', () => {
        const hostile = '<a href="javascript:alert(1)">click</a>';
        const clean = content.safeHTML(hostile);
        expect(clean).not.toContain('javascript:');
      });

      it('preserves safe formatting tags', () => {
        const input = '<p><strong>bold</strong> and <em>italic</em></p>';
        const clean = content.safeHTML(input);
        expect(clean).toContain('<strong>bold</strong>');
        expect(clean).toContain('<em>italic</em>');
      });
    });
  });

  // ---------------------------------------------------------------------------
  describe('isGmailFormNavigation()', () => {
    const originalLocation = window.location;

    afterEach(() => {
      // Restore hostname if mutated
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: originalLocation,
      });
    });

    function setHostname(hostname) {
      Object.defineProperty(window, 'location', {
        configurable: true,
        value: { ...originalLocation, hostname },
      });
    }

    it('returns true for Tab on input inside form on mail.google.com', () => {
      setHostname('mail.google.com');
      const form = document.createElement('form');
      const input = document.createElement('input');
      input.name = 'to';
      form.appendChild(input);
      document.body.appendChild(form);

      expect(content.isGmailFormNavigation(input, 'Tab')).toBe(true);
    });

    it('returns false for Tab on contenteditable body (compose body)', () => {
      setHostname('mail.google.com');
      const editable = document.createElement('div');
      editable.setAttribute('contenteditable', 'true');
      document.body.appendChild(editable);

      expect(content.isGmailFormNavigation(editable, 'Tab')).toBe(false);
    });

    it('returns false for non-Tab trigger key', () => {
      setHostname('mail.google.com');
      const form = document.createElement('form');
      const input = document.createElement('input');
      form.appendChild(input);
      document.body.appendChild(form);

      expect(content.isGmailFormNavigation(input, 'Space')).toBe(false);
    });

    it('returns false on other hostnames', () => {
      setHostname('example.com');
      const form = document.createElement('form');
      const input = document.createElement('input');
      form.appendChild(input);
      document.body.appendChild(form);

      expect(content.isGmailFormNavigation(input, 'Tab')).toBe(false);
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

    describe('detectEditorFramework()', () => {
      it('detects ProseMirror by classname on ancestor', () => {
        const editor = document.createElement('div');
        editor.className = 'ProseMirror';
        const inner = document.createElement('span');
        editor.appendChild(inner);
        document.body.appendChild(editor);

        expect(content.detectEditorFramework(inner)).toBe('prosemirror');
      });

      it('detects Lexical by data attribute', () => {
        const editor = document.createElement('div');
        editor.dataset.lexicalEditor = 'true';
        const inner = document.createElement('p');
        editor.appendChild(inner);
        document.body.appendChild(editor);

        expect(content.detectEditorFramework(inner)).toBe('lexical');
      });

      it('detects Slate by data attribute', () => {
        const editor = document.createElement('div');
        editor.dataset.slateEditor = 'true';
        document.body.appendChild(editor);

        expect(content.detectEditorFramework(editor)).toBe('slate');
      });

      it('returns null for plain contenteditable (Gmail, etc.)', () => {
        const editor = document.createElement('div');
        editor.setAttribute('contenteditable', 'true');
        document.body.appendChild(editor);

        expect(content.detectEditorFramework(editor)).toBeNull();
      });
    });

    it('routes through execCommand when ProseMirror is detected', () => {
      const editor = document.createElement('div');
      editor.className = 'ProseMirror';
      editor.setAttribute('contenteditable', 'true');
      const textNode = document.createTextNode('hello //sig');
      editor.appendChild(textNode);
      document.body.appendChild(editor);

      const range = document.createRange();
      range.setStart(textNode, textNode.length);
      range.setEnd(textNode, textNode.length);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);

      // jsdom doesn't implement execCommand natively; attach + spy.
      const execSpy = jest.fn(() => true);
      const original = document.execCommand;
      document.execCommand = execSpy;

      try {
        content.replaceInContentEditable(editor, '//sig', 'Popa', null);
        expect(execSpy).toHaveBeenCalledWith('insertText', false, 'Popa');
      } finally {
        if (original) document.execCommand = original;
        else delete document.execCommand;
      }
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

  // ---------------------------------------------------------------------------
  describe('extractCursorMarker()', () => {
    it('returns unchanged text when no marker present', () => {
      const { text, cursorOffset } = content.extractCursorMarker('Hello World');
      expect(text).toBe('Hello World');
      expect(cursorOffset).toBeNull();
    });

    it('removes marker and returns its position', () => {
      const { text, cursorOffset } = content.extractCursorMarker('Dear $|$,');
      expect(text).toBe('Dear ,');
      expect(cursorOffset).toBe(5);
    });

    it('handles marker at start', () => {
      const { text, cursorOffset } = content.extractCursorMarker('$|$rest');
      expect(text).toBe('rest');
      expect(cursorOffset).toBe(0);
    });

    it('handles marker at end', () => {
      const { text, cursorOffset } = content.extractCursorMarker('start $|$');
      expect(text).toBe('start ');
      expect(cursorOffset).toBe(6);
    });

    it('only removes the first marker (additional ones preserved)', () => {
      const { text, cursorOffset } = content.extractCursorMarker('a$|$b$|$c');
      expect(text).toBe('ab$|$c');
      expect(cursorOffset).toBe(1);
    });
  });

  describe('replaceInTextInput() with cursor marker', () => {
    it('lands caret at marker position after expansion', () => {
      const input = document.createElement('input');
      input.value = '//sig';
      document.body.appendChild(input);
      input.setSelectionRange(input.value.length, input.value.length);

      content.replaceInTextInput(input, '//sig', 'Dear $|$, regards');

      expect(input.value).toBe('Dear , regards');
      expect(input.selectionStart).toBe('Dear '.length);
      expect(input.selectionEnd).toBe('Dear '.length);
    });
  });

  // ---------------------------------------------------------------------------
  describe('processDateMacros()', () => {
    const fixedDate = new Date(2026, 3, 24, 14, 30); // 2026-04-24 14:30 local

    it('passes through strings without macros', () => {
      expect(content.processDateMacros('hello', fixedDate)).toBe('hello');
    });

    it('replaces [[date]] with default format', () => {
      const result = content.processDateMacros('Today: [[date]]', fixedDate);
      expect(result).toContain('2026');
      expect(result).not.toContain('[[date]]');
    });

    it('replaces [[date:DD.MM.YYYY]] with custom format', () => {
      const result = content.processDateMacros('[[date:DD.MM.YYYY]]', fixedDate);
      expect(result).toBe('24.04.2026');
    });

    it('applies +7d offset', () => {
      const result = content.processDateMacros('[[date+7d:DD.MM.YYYY]]', fixedDate);
      expect(result).toBe('01.05.2026');
    });

    it('applies -30d offset', () => {
      const result = content.processDateMacros('[[date-30d:DD.MM.YYYY]]', fixedDate);
      expect(result).toBe('25.03.2026');
    });

    it('applies +1m and +1y offset', () => {
      expect(content.processDateMacros('[[date+1m:DD.MM.YYYY]]', fixedDate)).toBe('24.05.2026');
      expect(content.processDateMacros('[[date+1y:DD.MM.YYYY]]', fixedDate)).toBe('24.04.2027');
    });

    it('[[time]] returns HH:mm', () => {
      expect(content.processDateMacros('[[time]]', fixedDate)).toBe('14:30');
    });

    it('preserves unknown tokens', () => {
      expect(content.processDateMacros('hello [[foo]]', fixedDate)).toBe('hello [[foo]]');
    });

    it('handles multiple macros in one string', () => {
      const result = content.processDateMacros(
        'From [[date:DD.MM.YYYY]] to [[date+7d:DD.MM.YYYY]]',
        fixedDate
      );
      expect(result).toBe('From 24.04.2026 to 01.05.2026');
    });
  });

  // ---------------------------------------------------------------------------
  describe('processSystemVars()', () => {
    const friday = new Date(2026, 3, 24, 14, 30); // 2026-04-24 Friday 14:30
    const morning = new Date(2026, 3, 24, 8, 0);  // 08:00
    const evening = new Date(2026, 3, 24, 20, 0); // 20:00

    beforeEach(() => {
      // Mock chrome.storage.local + navigator.clipboard
      global.chrome = global.chrome || {};
      global.chrome.storage = {
        local: {
          get: jest.fn().mockResolvedValue({ username: 'cosmin' }),
        },
      };
      global.navigator = global.navigator || {};
      global.navigator.clipboard = {
        readText: jest.fn().mockResolvedValue('clipped text'),
      };
    });

    it('passes through strings without system vars', async () => {
      expect(await content.processSystemVars('hello', friday)).toBe('hello');
    });

    it('[[day]] returns Romanian weekday name', async () => {
      expect(await content.processSystemVars('Azi e [[day]]', friday)).toBe('Azi e Vineri');
    });

    it('[[greeting]] picks Bună ziua at 14:30', async () => {
      expect(await content.processSystemVars('[[greeting]]', friday)).toBe('Bună ziua');
    });

    it('[[greeting]] picks Bună dimineața before 11:00', async () => {
      expect(await content.processSystemVars('[[greeting]]', morning)).toBe('Bună dimineața');
    });

    it('[[greeting]] picks Bună seara at 18:00+', async () => {
      expect(await content.processSystemVars('[[greeting]]', evening)).toBe('Bună seara');
    });

    it('[[user]] reads from chrome.storage.local', async () => {
      const result = await content.processSystemVars('Salut [[user]]', friday);
      expect(result).toBe('Salut cosmin');
    });

    it('[[user]] returns empty string when storage missing', async () => {
      global.chrome.storage.local.get.mockResolvedValueOnce({});
      expect(await content.processSystemVars('[[user]]', friday)).toBe('');
    });

    it('[[clipboard]] reads from navigator.clipboard', async () => {
      const result = await content.processSystemVars('Pasted: [[clipboard]]', friday);
      expect(result).toBe('Pasted: clipped text');
    });

    it('[[clipboard]] returns empty string on permission denial', async () => {
      global.navigator.clipboard.readText.mockRejectedValueOnce(new Error('NotAllowedError'));
      expect(await content.processSystemVars('[[clipboard]]', friday)).toBe('');
    });

    it('[[random:A|B|C]] picks one of the options', async () => {
      const result = await content.processSystemVars('[[random:Mersi|Mulțumesc|Cu drag]]', friday);
      expect(['Mersi', 'Mulțumesc', 'Cu drag']).toContain(result);
    });

    it('[[random]] without args returns empty string', async () => {
      expect(await content.processSystemVars('[[random]]', friday)).toBe('');
    });

    it('handles multiple system vars in one string', async () => {
      const result = await content.processSystemVars('[[greeting]] [[user]]!', friday);
      expect(result).toBe('Bună ziua cosmin!');
    });

    it('preserves unknown system vars', async () => {
      expect(await content.processSystemVars('hello [[foo]]', friday)).toBe('hello [[foo]]');
    });

    it('does not re-process replacement text containing [[...]]', async () => {
      // _readClipboard returns text that LOOKS LIKE a system var
      global.navigator.clipboard.readText.mockResolvedValueOnce('[[day]]');
      const result = await content.processSystemVars('Got: [[clipboard]]', friday);
      // Should NOT recurse and replace [[day]] inside the clipboard content
      expect(result).toBe('Got: [[day]]');
    });

    it('[[select:A|B|C]] returns option matching numeric prompt answer', async () => {
      const promptSpy = jest.spyOn(global, 'prompt').mockReturnValueOnce('2');
      const result = await content.processSystemVars('[[select:Mersi|Multumesc|Cu drag]]', friday);
      expect(result).toBe('Multumesc');
      promptSpy.mockRestore();
    });

    it('[[select:A|B|C]] accepts literal option text', async () => {
      const promptSpy = jest.spyOn(global, 'prompt').mockReturnValueOnce('Cu drag');
      const result = await content.processSystemVars('[[select:Mersi|Multumesc|Cu drag]]', friday);
      expect(result).toBe('Cu drag');
      promptSpy.mockRestore();
    });

    it('[[select:A|B|C]] returns empty on cancel', async () => {
      const promptSpy = jest.spyOn(global, 'prompt').mockReturnValueOnce(null);
      const result = await content.processSystemVars('[[select:A|B]]', friday);
      expect(result).toBe('');
      promptSpy.mockRestore();
    });

    it('[[select]] with single option auto-selects without prompting', async () => {
      const promptSpy = jest.spyOn(global, 'prompt');
      const result = await content.processSystemVars('[[select:Only one]]', friday);
      expect(result).toBe('Only one');
      expect(promptSpy).not.toHaveBeenCalled();
      promptSpy.mockRestore();
    });

    it('multiple [[select]] prompts run sequentially in order', async () => {
      const calls = [];
      const promptSpy = jest.spyOn(global, 'prompt').mockImplementation((msg) => {
        calls.push(msg);
        return '1';  // always pick first option
      });
      const result = await content.processSystemVars('[[select:A|B]] then [[select:C|D]]', friday);
      expect(result).toBe('A then C');
      expect(calls).toHaveLength(2);
      // First prompt mentions A|B, second mentions C|D
      expect(calls[0]).toContain('A');
      expect(calls[1]).toContain('C');
      promptSpy.mockRestore();
    });

    it('[[recipient]] returns empty when no site parser matches', async () => {
      // Default jsdom location is "localhost", no parser registered
      // — should gracefully return empty string
      const result = await content.processSystemVars('Hi [[recipient]]', friday);
      expect(result).toBe('Hi ');
    });
  });

  // ---------------------------------------------------------------------------
  describe('isTriggerKey()', () => {
    it('key mode: matches configured triggerKey only', () => {
      const s = { triggerMode: 'key', triggerKey: 'Tab' };
      expect(content.isTriggerKey({ key: 'Tab' }, s)).toBe(true);
      expect(content.isTriggerKey({ key: ' ' }, s)).toBe(false);
      expect(content.isTriggerKey({ key: 'Enter' }, s)).toBe(false);
    });

    it('key mode: custom triggerKey respected', () => {
      const s = { triggerMode: 'key', triggerKey: 'Enter' };
      expect(content.isTriggerKey({ key: 'Enter' }, s)).toBe(true);
      expect(content.isTriggerKey({ key: 'Tab' }, s)).toBe(false);
    });

    it('space mode: matches Space OR Enter', () => {
      const s = { triggerMode: 'space' };
      expect(content.isTriggerKey({ key: ' ' }, s)).toBe(true);
      expect(content.isTriggerKey({ key: 'Enter' }, s)).toBe(true);
    });

    it('space mode: ignores Tab (so Tab navigation still works)', () => {
      const s = { triggerMode: 'space' };
      expect(content.isTriggerKey({ key: 'Tab' }, s)).toBe(false);
    });

    it('defaults to key mode when triggerMode unspecified', () => {
      expect(content.isTriggerKey({ key: 'Tab' }, { triggerKey: 'Tab' })).toBe(true);
    });
  });

  // ---------------------------------------------------------------------------
  describe('processSnippetNesting()', () => {
    it('passes through text without nesting tokens', () => {
      expect(content.processSnippetNesting('hello', {})).toBe('hello');
    });

    it('expands a single nested snippet', () => {
      const map = { sig: { value: 'Cosmin Popa' } };
      expect(
        content.processSnippetNesting('Best,\n[[%s(sig)]]', map)
      ).toBe('Best,\nCosmin Popa');
    });

    it('expands multiple nested references', () => {
      const map = {
        greet: { value: 'Salut' },
        sig: { value: 'Cosmin' },
      };
      expect(
        content.processSnippetNesting('[[%s(greet)]], [[%s(sig)]]', map)
      ).toBe('Salut, Cosmin');
    });

    it('expands 2-level nesting', () => {
      const map = {
        sig: { value: 'Best,\n[[%s(name)]]' },
        name: { value: 'Cosmin Popa' },
      };
      expect(content.processSnippetNesting('[[%s(sig)]]', map)).toBe('Best,\nCosmin Popa');
    });

    it('detects self-reference cycle', () => {
      const map = {
        loop: { value: 'A [[%s(loop)]] B' },
      };
      const result = content.processSnippetNesting('[[%s(loop)]]', map);
      expect(result).toContain('[cycle:loop]');
    });

    it('detects mutual-reference cycle', () => {
      const map = {
        a: { value: '[[%s(b)]]' },
        b: { value: '[[%s(a)]]' },
      };
      const result = content.processSnippetNesting('[[%s(a)]]', map);
      expect(result).toContain('[cycle:a]');
    });

    it('marks missing snippets explicitly', () => {
      const result = content.processSnippetNesting('pre [[%s(ghost)]] post', {});
      expect(result).toBe('pre [missing:ghost] post');
    });

    it('stops at depth limit (5)', () => {
      // Build a 7-deep chain
      const map = {};
      for (let i = 0; i < 7; i++) {
        map[`n${i}`] = { value: i === 6 ? 'LEAF' : `[[%s(n${i + 1})]]` };
      }
      const result = content.processSnippetNesting('[[%s(n0)]]', map);
      // Should not contain LEAF (depth-capped before reaching it)
      expect(result).not.toContain('LEAF');
    });

    it('uses html_value when value is missing', () => {
      const map = { h: { html_value: '<p>HTML body</p>' } };
      expect(content.processSnippetNesting('[[%s(h)]]', map)).toBe('<p>HTML body</p>');
    });
  });

  // ---------------------------------------------------------------------------
  describe('extractPlaceholders()', () => {
    it('returns [] for text without placeholders', () => {
      expect(content.extractPlaceholders('hello world')).toEqual([]);
    });

    it('extracts a single name-only placeholder', () => {
      expect(content.extractPlaceholders('Hi {{name}}')).toEqual([
        { name: 'name', label: 'name', default: '' },
      ]);
    });

    it('extracts name + label', () => {
      expect(content.extractPlaceholders('{{desc:Description}}')).toEqual([
        { name: 'desc', label: 'Description', default: '' },
      ]);
    });

    it('extracts name + label + default', () => {
      expect(content.extractPlaceholders('{{num:Ticket ID|TICKET-001}}')).toEqual([
        { name: 'num', label: 'Ticket ID', default: 'TICKET-001' },
      ]);
    });

    it('deduplicates repeated names', () => {
      const fields = content.extractPlaceholders('{{x}} and {{x:Later}} again {{y}}');
      expect(fields.map(f => f.name)).toEqual(['x', 'y']);
    });

    it('ignores empty {{}}', () => {
      expect(content.extractPlaceholders('hi {{}}')).toEqual([]);
    });
  });

  describe('substitutePlaceholders()', () => {
    it('replaces each placeholder with its value', () => {
      expect(
        content.substitutePlaceholders('Hi {{name}}!', { name: 'Cosmin' })
      ).toBe('Hi Cosmin!');
    });

    it('replaces all occurrences of the same placeholder', () => {
      expect(
        content.substitutePlaceholders('{{x}} + {{x}} = 2x', { x: '7' })
      ).toBe('7 + 7 = 2x');
    });

    it('substitutes empty string when value missing', () => {
      expect(
        content.substitutePlaceholders('Hi {{name}}', {})
      ).toBe('Hi ');
    });
  });

  describe('promptForPlaceholders()', () => {
    it('collects answers via injected askFn', () => {
      const fields = [
        { name: 'a', label: 'A', default: 'dA' },
        { name: 'b', label: 'B', default: '' },
      ];
      const ask = jest.fn()
        .mockReturnValueOnce('ans1')
        .mockReturnValueOnce('ans2');
      const result = content.promptForPlaceholders(fields, ask);
      expect(result).toEqual({ values: { a: 'ans1', b: 'ans2' } });
      expect(ask).toHaveBeenNthCalledWith(1, 'A', 'dA');
      expect(ask).toHaveBeenNthCalledWith(2, 'B', '');
    });

    it('returns cancelled when askFn returns null', () => {
      const ask = jest.fn().mockReturnValueOnce(null);
      const result = content.promptForPlaceholders(
        [{ name: 'x', label: 'X', default: '' }],
        ask
      );
      expect(result).toEqual({ cancelled: true });
    });

    it('stops asking after first cancel (no more prompts)', () => {
      const ask = jest.fn()
        .mockReturnValueOnce('ok')
        .mockReturnValueOnce(null);
      content.promptForPlaceholders(
        [
          { name: 'a', label: 'A', default: '' },
          { name: 'b', label: 'B', default: '' },
          { name: 'c', label: 'C', default: '' },
        ],
        ask
      );
      expect(ask).toHaveBeenCalledTimes(2);  // stopped after cancel on 'b'
    });
  });

  // ---------------------------------------------------------------------------
  describe('filterShortcuts()', () => {
    const map = {
      sig: { value: 'Cosmin Popa', id: 1 },
      addr: { value: 'Str. Exemplu 10', id: 2 },
      phone: { value: '+40 700 000 000', id: 3 },
    };

    it('returns all entries (truncated) when query empty', () => {
      const result = content.filterShortcuts('', map);
      expect(result).toHaveLength(3);
    });

    it('ranks exact key match highest', () => {
      const result = content.filterShortcuts('sig', map);
      expect(result[0].key).toBe('sig');
    });

    it('matches prefix before substring', () => {
      const m = {
        abc: { value: 'x' },
        xabcy: { value: 'y' },
      };
      const result = content.filterShortcuts('abc', m);
      expect(result[0].key).toBe('abc');
      expect(result[1].key).toBe('xabcy');
    });

    it('falls back to value text match', () => {
      const result = content.filterShortcuts('Popa', map);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].key).toBe('sig');
    });

    it('returns empty for no matches', () => {
      const result = content.filterShortcuts('zzzzzz', map);
      expect(result).toHaveLength(0);
    });

    it('falls back to fuzzy subsequence when no substring match', () => {
      // 'pne' is not a substring of 'phone' but chars appear in order
      const result = content.filterShortcuts('pne', map);
      expect(result.length).toBeGreaterThan(0);
      expect(result[0].key).toBe('phone');
    });

    it('ranks substring above fuzzy fallback', () => {
      const m = {
        myphone: { value: 'x' },          // substring "phn" — no, fuzzy
        phn: { value: 'y' },              // exact substring "phn"? no, equals
      };
      // Query 'phn' equals key 'phn' -> exact match wins over fuzzy on 'myphone'
      const result = content.filterShortcuts('phn', m);
      expect(result[0].key).toBe('phn');
    });

    it('does not return fuzzy hits below threshold', () => {
      const m = { abcdefghij: { value: 'long key' } };
      // Query "xyz" has no chars in haystack -> 0 score -> excluded
      const result = content.filterShortcuts('xyz', m);
      expect(result).toHaveLength(0);
    });
  });

  describe('openCommandPalette() / closeCommandPalette()', () => {
    afterEach(() => {
      content.closeCommandPalette();
    });

    it('mounts a shadow-DOM host in the document', () => {
      content._setShortcuts({ foo: { value: 'Bar' } });
      content.openCommandPalette();
      const host = document.getElementById('autotext-palette-host');
      expect(host).not.toBeNull();
      expect(host.shadowRoot).toBeNull();  // closed shadow, shadowRoot isn't exposed
    });

    it('close removes the host from DOM', () => {
      content._setShortcuts({ foo: { value: 'Bar' } });
      content.openCommandPalette();
      content.closeCommandPalette();
      expect(document.getElementById('autotext-palette-host')).toBeNull();
    });

    it('opening twice is a no-op (single instance)', () => {
      content._setShortcuts({ foo: { value: 'Bar' } });
      content.openCommandPalette();
      content.openCommandPalette();
      const hosts = document.querySelectorAll('#autotext-palette-host');
      expect(hosts).toHaveLength(1);
    });
  });
});
