// SUPER SIMPLE TEST VERSION - Just to see if extension works at all

console.log('🔥 TEST EXTENSION LOADED! 🔥');
console.log('If you see this message, the content script is running.');

// Test 1: Can we detect keyboard events?
document.addEventListener('keydown', (e) => {
  console.log(`Key pressed: "${e.key}" (code: ${e.code})`);

  if (e.key === 'Tab') {
    console.log('🎯 TAB KEY DETECTED!!!');

    // Let's see what element has focus
    const el = document.activeElement;
    console.log('Active element:', el.tagName, el.type || '');

    // If it's in a text field, try to get the value
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
      console.log('Current value:', el.value);
      console.log('Cursor position:', el.selectionStart);

      // Get last word before cursor
      const text = el.value.substring(0, el.selectionStart);
      const match = text.match(/(\S+)$/);
      const lastWord = match ? match[1] : '';
      console.log('Last word before cursor:', lastWord);

      // Check if it's "b"
      if (lastWord === 'b') {
        console.log('🚀 FOUND "b"! Preventing Tab and replacing...');
        e.preventDefault();

        const before = el.value.substring(0, el.selectionStart);
        const after = el.value.substring(el.selectionStart);
        const newBefore = before.slice(0, -1) + 'Bună ziua,';

        el.value = newBefore + after;
        el.selectionStart = el.selectionEnd = newBefore.length;

        console.log('✅ REPLACEMENT DONE!');
      }
    }
  }
}, true);

console.log('✅ Event listener attached. Try typing "b" then Tab in any text field!');
