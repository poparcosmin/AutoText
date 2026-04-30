/**
 * @jest-environment jsdom
 */

const content = require('../content.js');

describe('Site-specific behavior', () => {
  describe('isGmailFormNavigation', () => {
    let originalLocation;

    beforeEach(() => {
      originalLocation = window.location;
      delete window.location;
      window.location = new URL('https://mail.google.com');
    });

    afterEach(() => {
      window.location = originalLocation;
    });

    it('returns true for Tab in Gmail form input', () => {
      const form = document.createElement('form');
      const input = document.createElement('input');
      form.appendChild(input);
      document.body.appendChild(form);

      expect(content.isGmailFormNavigation(input, 'Tab')).toBe(true);
    });

    it('returns false for Tab in Gmail body (not in form)', () => {
      const div = document.createElement('div');
      div.contentEditable = true;
      document.body.appendChild(div);

      expect(content.isGmailFormNavigation(div, 'Tab')).toBe(false);
    });

    it('returns false for other keys in Gmail form', () => {
      const form = document.createElement('form');
      const input = document.createElement('input');
      form.appendChild(input);
      document.body.appendChild(form);

      expect(content.isGmailFormNavigation(input, ' ')).toBe(false);
    });

    it('returns false for Tab on other hosts', () => {
      delete window.location;
      window.location = new URL('https://example.com');
      const form = document.createElement('form');
      const input = document.createElement('input');
      form.appendChild(input);
      document.body.appendChild(form);

      expect(content.isGmailFormNavigation(input, 'Tab')).toBe(false);
    });
  });

  describe('isTriggerKey', () => {
    it('handles "key" mode with default Tab', () => {
      const settings = { triggerMode: 'key', triggerKey: 'Tab' };
      expect(content.isTriggerKey({ key: 'Tab' }, settings)).toBe(true);
      expect(content.isTriggerKey({ key: ' ' }, settings)).toBe(false);
    });

    it('handles "key" mode with custom key', () => {
      const settings = { triggerMode: 'key', triggerKey: 'Escape' };
      expect(content.isTriggerKey({ key: 'Escape' }, settings)).toBe(true);
      expect(content.isTriggerKey({ key: 'Tab' }, settings)).toBe(false);
    });

    it('handles "space" mode', () => {
      const settings = { triggerMode: 'space' };
      expect(content.isTriggerKey({ key: ' ' }, settings)).toBe(true);
      expect(content.isTriggerKey({ key: 'Enter' }, settings)).toBe(true);
      expect(content.isTriggerKey({ key: 'Tab' }, settings)).toBe(false);
    });
  });

  describe('isBlacklisted', () => {
    let originalLocation;

    beforeEach(() => {
      originalLocation = window.location;
      delete window.location;
    });

    afterEach(() => {
      window.location = originalLocation;
    });

    it('returns true if host is in blacklist', () => {
      window.location = new URL('https://facebook.com');
      content._setSettings({ blacklistedSites: ['facebook.com'] });
      expect(content.isBlacklisted()).toBe(true);
    });

    it('returns false if host is NOT in blacklist', () => {
      window.location = new URL('https://gmail.com');
      content._setSettings({ blacklistedSites: ['facebook.com'] });
      expect(content.isBlacklisted()).toBe(false);
    });

    it('handles partial matches', () => {
      window.location = new URL('https://sub.facebook.com');
      content._setSettings({ blacklistedSites: ['facebook.com'] });
      expect(content.isBlacklisted()).toBe(true);
    });
  });
});

describe('Placeholder logic', () => {
  describe('extractPlaceholders', () => {
    it('extracts placeholders with labels', () => {
      const input = 'Hello {{name:User}}, welcome to {{prod:Product}}!';
      const result = content.extractPlaceholders(input);
      expect(result).toEqual([
        { name: 'name', label: 'User', default: '' },
        { name: 'prod', label: 'Product', default: '' }
      ]);
    });

    it('handles placeholders without labels', () => {
      const input = 'Contact {{email}}';
      const result = content.extractPlaceholders(input);
      expect(result).toEqual([
        { name: 'email', label: 'email', default: '' }
      ]);
    });

    it('returns empty array when no placeholders', () => {
      expect(content.extractPlaceholders('Plain text')).toEqual([]);
    });
  });

  describe('substitutePlaceholders', () => {
    it('replaces placeholders with provided values', () => {
      const input = 'Hello {{name}}, welcome to {{prod}}!';
      const values = { name: 'Alice', prod: 'AutoText' };
      expect(content.substitutePlaceholders(input, values)).toBe('Hello Alice, welcome to AutoText!');
    });

    it('uses empty string for missing values', () => {
      const input = 'Hello {{name}}';
      expect(content.substitutePlaceholders(input, {})).toBe('Hello ');
    });
  });
});

describe('Additional logic', () => {
  describe('promptForPlaceholders', () => {
    it('collects values from askFn', () => {
      const fields = [
        { name: 'name', label: 'User', default: 'John' },
        { name: 'city', label: 'City', default: 'NY' }
      ];
      const askFn = jest.fn()
        .mockReturnValueOnce('Alice')
        .mockReturnValueOnce('London');
      
      const result = content.promptForPlaceholders(fields, askFn);
      expect(result).toEqual({ values: { name: 'Alice', city: 'London' } });
      expect(askFn).toHaveBeenCalledTimes(2);
      expect(askFn).toHaveBeenCalledWith('User', 'John');
      expect(askFn).toHaveBeenCalledWith('City', 'NY');
    });

    it('returns cancelled if askFn returns null', () => {
      const fields = [{ name: 'name', label: 'User', default: '' }];
      const askFn = jest.fn().mockReturnValue(null);
      
      const result = content.promptForPlaceholders(fields, askFn);
      expect(result).toEqual({ cancelled: true });
    });
  });

  describe('filterShortcuts', () => {
    const shortcuts = {
      sig: { value: 'Signature' },
      hello: { value: 'Hello World' },
      bye: { value: 'Goodbye' }
    };

    it('filters by key', () => {
      const result = content.filterShortcuts('he', shortcuts);
      expect(result).toHaveLength(1);
      expect(result[0].key).toBe('hello');
    });

    it('filters by value content', () => {
      const result = content.filterShortcuts('world', shortcuts);
      expect(result).toHaveLength(1);
      expect(result[0].key).toBe('hello');
    });

    it('returns up to 50 results', () => {
      const manyShortcuts = {};
      for (let i = 0; i < 60; i++) manyShortcuts['k'+i] = { value: 'test' };
      const result = content.filterShortcuts('test', manyShortcuts);
      expect(result).toHaveLength(50);
    });
  });
});

describe('Editor detection and replacement', () => {
  describe('detectEditorFramework', () => {
    it('detects ProseMirror', () => {
      const el = document.createElement('div');
      el.classList.add('ProseMirror');
      expect(content.detectEditorFramework(el)).toBe('prosemirror');
    });

    it('detects Lexical', () => {
      const el = document.createElement('div');
      el.dataset.lexicalEditor = 'true';
      expect(content.detectEditorFramework(el)).toBe('lexical');
    });

    it('returns null for unknown', () => {
      const el = document.createElement('div');
      expect(content.detectEditorFramework(el)).toBeNull();
    });
  });

  describe('setNativeValue', () => {
    it('sets value using property descriptor', () => {
      const input = document.createElement('input');
      content.setNativeValue(input, 'new value');
      expect(input.value).toBe('new value');
    });
  });

  describe('replaceInTextInput', () => {
    it('replaces shortcut with expansion in INPUT', () => {
      const input = document.createElement('input');
      input.value = 'hello //sig';
      document.body.appendChild(input);
      input.focus();
      input.setSelectionRange(11, 11);
      
      content.replaceInTextInput(input, '//sig', 'Signature');
      
      expect(input.value).toBe('hello Signature');
    });
  });
});

describe('Date Macros', () => {
  it('handles [[date]]', () => {
    const now = new Date(2026, 3, 29); // April 29, 2026
    const result = content.processDateMacros('Today is [[date]]', now);
    expect(result).toBe('Today is 29.04.2026');
  });

  it('handles [[date+3d]]', () => {
    const now = new Date(2026, 3, 29);
    const result = content.processDateMacros('In 3 days: [[date+3d]]', now);
    expect(result).toBe('In 3 days: 02.05.2026');
  });

  it('handles [[date:YYYY-MM-DD]]', () => {
    const now = new Date(2026, 3, 29);
    const result = content.processDateMacros('ISO: [[date:YYYY-MM-DD]]', now);
    expect(result).toBe('ISO: 2026-04-29');
  });
});

describe('System Variables and Conditionals', () => {
  describe('processSystemVars', () => {
    it('handles [[random:...]]', async () => {
      const input = 'Pick: [[random:A|B|C]]';
      const result = await content.processSystemVars(input);
      expect(['Pick: A', 'Pick: B', 'Pick: C']).toContain(result);
    });

    it('handles [[day]]', async () => {
      const now = new Date(2026, 3, 29); // Wednesday (Miercuri)
      const input = 'Azi e [[day]]';
      const result = await content.processSystemVars(input, now);
      expect(result).toBe('Azi e Miercuri');
    });
  });

  describe('processConditionals', () => {
    it('handles simple truthy value', () => {
      const input = '[[if: somevalue ]]YES[[else]]NO[[endif]]';
      expect(content.processConditionals(input)).toBe('YES');
    });

    it('handles simple falsy value', () => {
      const input = '[[if:  ]]YES[[else]]NO[[endif]]';
      expect(content.processConditionals(input)).toBe('NO');
    });

    it('handles == operator', () => {
      const input = '[[if: foo == foo ]]YES[[endif]]';
      expect(content.processConditionals(input)).toBe('YES');
    });

    it('handles != operator', () => {
      const input = '[[if: foo != bar ]]YES[[endif]]';
      expect(content.processConditionals(input)).toBe('YES');
    });
  });
});

describe('Cursor Marker', () => {
  it('extracts marker and returns offset', () => {
    const input = 'Hello $|$ World';
    const { text, cursorOffset } = content.extractCursorMarker(input);
    expect(text).toBe('Hello  World');
    expect(cursorOffset).toBe(6);
  });

  it('returns null offset if no marker', () => {
    const input = 'No marker';
    const { text, cursorOffset } = content.extractCursorMarker(input);
    expect(text).toBe('No marker');
    expect(cursorOffset).toBeNull();
  });
});

describe('safeHTML', () => {
  it('passes through text when DOMPurify matches', () => {
    const dirty = '<b>Bold</b><script>alert(1)</script>';
    expect(content.safeHTML(dirty)).toBe(dirty);
  });
});

describe('Date Offsets (Working Days)', () => {
  it('handles [[date+3wd]] skipping weekends', () => {
    const friday = new Date(2026, 4, 1);
    expect(friday.getDay()).toBe(5);
    const result = content.processDateMacros('[[date+3wd]]', friday);
    expect(result).toBe('06.05.2026');
  });

  it('handles [[date-1wd]] from Monday', () => {
    const monday = new Date(2026, 4, 4);
    expect(monday.getDay()).toBe(1);
    const result = content.processDateMacros('[[date-1wd]]', monday);
    expect(result).toBe('01.05.2026');
  });
});

describe('ContentEditable Replacement', () => {
  it('falls back to Range API if execCommand is not handled', () => {
    const div = document.createElement('div');
    div.contentEditable = true;
    document.body.appendChild(div);
    div.focus();
    
    const mockRange = {
      deleteContents: jest.fn(),
      insertNode: jest.fn(),
      setStart: jest.fn(),
      setEnd: jest.fn(),
      collapse: jest.fn(),
      createContextualFragment: jest.fn().mockReturnValue(document.createDocumentFragment()),
    };
    window.getSelection = jest.fn().mockReturnValue({
      rangeCount: 1,
      getRangeAt: jest.fn().mockReturnValue(mockRange),
      removeAllRanges: jest.fn(),
      addRange: jest.fn(),
    });
    document.execCommand = jest.fn().mockReturnValue(false); // Force fallback
    
    content.replaceInContentEditable(div, '//sig', 'Signature', '<b>Signature</b>');
    
    expect(mockRange.deleteContents).toHaveBeenCalled();
    expect(mockRange.insertNode).toHaveBeenCalled();
  });
});
