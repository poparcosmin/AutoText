// Toggle between Plain Text and Rich Text (HTML) content fields
(function() {
    'use strict';

    function toggleContentFields() {
        const contentTypeSelect = document.querySelector('#id_content_type');
        if (!contentTypeSelect) return;

        const textSection = document.querySelector('.text-section');
        const htmlSection = document.querySelector('.html-section');

        if (!textSection || !htmlSection) return;

        const selectedType = contentTypeSelect.value;

        // Add/remove 'active' class based on content_type
        // Both sections remain visible, but styled differently
        if (selectedType === 'text') {
            textSection.classList.add('active');
            htmlSection.classList.remove('active');
        } else if (selectedType === 'html') {
            textSection.classList.remove('active');
            htmlSection.classList.add('active');
        }
    }

    // Run on page load
    document.addEventListener('DOMContentLoaded', function() {
        toggleContentFields();

        // Listen for changes on content_type select
        const contentTypeSelect = document.querySelector('#id_content_type');
        if (contentTypeSelect) {
            contentTypeSelect.addEventListener('change', toggleContentFields);
        }
    });

    // For TinyMCE, also run after it initializes
    if (window.django && window.django.jQuery) {
        django.jQuery(document).ready(function() {
            setTimeout(toggleContentFields, 100);
        });
    }
})();
