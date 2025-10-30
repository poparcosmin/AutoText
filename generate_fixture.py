#!/usr/bin/env python3
"""
Generate Django fixture from paff.yml for Birou shortcut set.

Transformations:
- Trigger: Remove leading backtick (`) from trigger
- Value: Plain text from replace
- HTML Value: HTML formatted text from replace
"""

import yaml
import json
import re
from datetime import datetime, timezone


def clean_trigger(trigger):
    """Remove leading backtick from trigger."""
    if trigger.startswith('`'):
        return trigger[1:]
    return trigger


def text_to_html(text):
    """
    Convert plain text to HTML with basic formatting.
    - Preserve line breaks
    - Convert URLs to links
    - Bold text in <b> tags
    """
    if not text:
        return ""

    # Remove any existing HTML tags if they're malformed
    # (some entries in YAML have incomplete HTML)
    text = text.strip()

    # If text already contains HTML tags, clean them up
    if '<b>' in text or '<font' in text:
        # Clean up incomplete tags
        text = text.replace('"', '')  # Remove trailing quotes
        text = text.strip()
        return text

    # Convert newlines to <br>
    html = text.replace('\n', '<br>')

    # Convert URLs to links
    url_pattern = r'(https?://[^\s\)]+)'
    html = re.sub(url_pattern, r'<a href="\1">\1</a>', html)

    return html


def generate_fixture(yaml_file, output_file, set_id=1):
    """
    Generate Django fixture from YAML file.

    Args:
        yaml_file: Path to paff.yml
        output_file: Path to output JSON fixture
        set_id: ID of the "birou" ShortcutSet (default: 1)
    """

    # Load YAML
    with open(yaml_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    fixtures = []

    # Process each match
    for idx, match in enumerate(data.get('matches', []), start=1):
        trigger = match.get('trigger', '')
        replace = match.get('replace', '')

        if not trigger or not replace:
            continue

        # Clean trigger (remove backtick)
        key = clean_trigger(trigger)

        # Plain text value
        value = replace.strip()

        # HTML formatted value
        html_value = text_to_html(value)

        # Create fixture entry
        fixture = {
            "model": "textsync.Shortcut",
            "pk": idx,
            "fields": {
                "key": key,
                "value": value,
                "html_value": html_value,
                "sets": [set_id],  # Birou set
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": None
            }
        }

        fixtures.append(fixture)

    # Write fixture to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)

    print(f"✅ Generated {len(fixtures)} shortcuts in {output_file}")
    print(f"   Set ID: {set_id} (birou)")
    print(f"\nTo load fixture:")
    print(f"   python manage.py loaddata {output_file}")


if __name__ == '__main__':
    generate_fixture(
        yaml_file='paff.yml',
        output_file='textsync/fixtures/birou_shortcuts.json',
        set_id=1  # ID of "birou" set - adjust if needed
    )
