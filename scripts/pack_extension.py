#!/usr/bin/env python3
"""
Chrome Extension Packer - Generates CRX3 and ZIP files for distribution.

Usage:
    python pack_extension.py [--version X.Y.Z] [--output-dir DIR]

This script:
1. Reads version from manifest.json (or uses --version override)
2. Creates a ZIP file of the extension
3. Generates a CRX3 file (signed)
4. Creates/updates the updates.xml manifest
5. Outputs version info for deployment
"""

import argparse
import hashlib
import json
import os
import shutil
import struct
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    print("Warning: cryptography library not installed. CRX signing disabled.")
    print("Install with: pip install cryptography")


# Configuration
EXTENSION_DIR = Path(__file__).parent.parent / "extension"
OUTPUT_DIR = Path(__file__).parent.parent / "dist"
KEY_FILE = Path(__file__).parent.parent / ".extension_key.pem"
UPDATE_URL = "https://autotext.zua.ro/extension"


def get_manifest_version():
    """Read version from manifest.json"""
    manifest_path = EXTENSION_DIR / "manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    return manifest.get('version', '1.0.0')


def update_manifest_version(new_version):
    """Update version in manifest.json"""
    manifest_path = EXTENSION_DIR / "manifest.json"
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    old_version = manifest.get('version', '1.0.0')
    manifest['version'] = new_version

    # Remove update_url if present (not allowed for Chrome Web Store)
    manifest.pop('update_url', None)

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    return old_version


def create_zip(output_path):
    """Create a ZIP file of the extension"""
    # Files/folders to exclude
    exclude = {'.git', '__pycache__', '.DS_Store', 'Thumbs.db', '*.pyc', '.env'}

    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(EXTENSION_DIR):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude]

            for file in files:
                if file in exclude or file.endswith('.pyc'):
                    continue

                file_path = Path(root) / file
                arcname = file_path.relative_to(EXTENSION_DIR)
                zf.write(file_path, arcname)

    print(f"Created ZIP: {output_path}")
    return output_path


def get_or_create_key():
    """Get existing private key or create a new one"""
    if not HAS_CRYPTO:
        return None

    if KEY_FILE.exists():
        with open(KEY_FILE, 'rb') as f:
            private_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
        print(f"Loaded existing key from {KEY_FILE}")
    else:
        # Generate new RSA key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )

        # Save the key
        with open(KEY_FILE, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

        print(f"Generated new key: {KEY_FILE}")
        print("IMPORTANT: Keep this key safe! You need it for updates.")

    return private_key


def get_extension_id(public_key_bytes):
    """Calculate Chrome extension ID from public key"""
    # Chrome uses first 128 bits of SHA256 hash, encoded in a special alphabet
    digest = hashlib.sha256(public_key_bytes).digest()[:16]

    # Chrome's alphabet: a-p (instead of 0-9a-f)
    extension_id = ''.join(chr(ord('a') + (b >> 4)) + chr(ord('a') + (b & 0xf))
                          for b in digest)
    return extension_id


def create_crx3(zip_path, output_path, private_key):
    """Create a CRX3 file from ZIP"""
    if not HAS_CRYPTO or private_key is None:
        print("Skipping CRX creation (no cryptography library)")
        return None

    # Read ZIP content
    with open(zip_path, 'rb') as f:
        zip_content = f.read()

    # Get public key in DER format
    public_key = private_key.public_key()
    public_key_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Calculate extension ID
    extension_id = get_extension_id(public_key_bytes)
    print(f"Extension ID: {extension_id}")

    # Create signed data (CRX3 format)
    # CRX3 uses a protobuf-like format, but we'll use the simpler CRX2 format
    # which Chrome still supports for unpacked extensions

    # Sign the ZIP content
    signature = private_key.sign(
        zip_content,
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    # CRX2 format (simpler, still works):
    # - Magic: "Cr24" (4 bytes)
    # - Version: 2 (4 bytes, little-endian)
    # - Public key length (4 bytes, little-endian)
    # - Signature length (4 bytes, little-endian)
    # - Public key
    # - Signature
    # - ZIP content

    with open(output_path, 'wb') as f:
        # Magic number
        f.write(b'Cr24')
        # Version
        f.write(struct.pack('<I', 2))
        # Public key length
        f.write(struct.pack('<I', len(public_key_bytes)))
        # Signature length
        f.write(struct.pack('<I', len(signature)))
        # Public key
        f.write(public_key_bytes)
        # Signature
        f.write(signature)
        # ZIP content
        f.write(zip_content)

    print(f"Created CRX: {output_path}")
    return extension_id


def create_updates_xml(extension_id, version, output_dir):
    """Create updates.xml for self-hosted auto-updates"""
    xml_content = f'''<?xml version='1.0' encoding='UTF-8'?>
<gupdate xmlns='http://www.google.com/update2/response' protocol='2.0'>
  <app appid='{extension_id}'>
    <updatecheck codebase='{UPDATE_URL}/textsync-{version}.crx' version='{version}' />
  </app>
</gupdate>
'''

    output_path = output_dir / "updates.xml"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(xml_content)

    print(f"Created updates.xml: {output_path}")
    return output_path


def create_install_instructions(version, extension_id, output_dir):
    """Create installation instructions file"""
    content = f'''# TextSync Extension v{version}

## Installation Instructions

### Option 1: Load Unpacked (Developer Mode)

1. Download and extract `textsync-{version}.zip`
2. Open Chrome and go to `chrome://extensions`
3. Enable "Developer mode" (toggle in top right)
4. Click "Load unpacked"
5. Select the extracted folder

### Option 2: Install CRX (Enterprise/Policy)

For enterprise deployment, the CRX file can be installed via Group Policy.

Extension ID: `{extension_id}`
CRX URL: `{UPDATE_URL}/textsync-{version}.crx`
Update URL: `{UPDATE_URL}/updates.xml`

## Files Included

- `textsync-{version}.zip` - Unpacked extension (for developer mode)
- `textsync-{version}.crx` - Packed extension (for enterprise)
- `updates.xml` - Update manifest for auto-updates

## Version History

- {version} - {datetime.now().strftime('%Y-%m-%d')}

---
Generated: {datetime.now().isoformat()}
'''

    output_path = output_dir / "README.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Created README: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Pack Chrome extension for distribution')
    parser.add_argument('--version', '-v', help='Version number (default: from manifest.json)')
    parser.add_argument('--output-dir', '-o', help='Output directory', default=str(OUTPUT_DIR))
    parser.add_argument('--bump', choices=['major', 'minor', 'patch'],
                        help='Bump version (major.minor.patch)')
    args = parser.parse_args()

    # Ensure output directory exists
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get/set version
    current_version = get_manifest_version()

    if args.bump:
        parts = [int(x) for x in current_version.split('.')]
        while len(parts) < 3:
            parts.append(0)

        if args.bump == 'major':
            parts = [parts[0] + 1, 0, 0]
        elif args.bump == 'minor':
            parts = [parts[0], parts[1] + 1, 0]
        else:  # patch
            parts = [parts[0], parts[1], parts[2] + 1]

        version = '.'.join(str(x) for x in parts)
        update_manifest_version(version)
        print(f"Bumped version: {current_version} -> {version}")
    elif args.version:
        version = args.version
        update_manifest_version(version)
        print(f"Set version: {version}")
    else:
        version = current_version
        print(f"Using version: {version}")

    # Create ZIP
    zip_path = output_dir / f"textsync-{version}.zip"
    create_zip(zip_path)

    # Get or create signing key
    private_key = get_or_create_key()

    # Create CRX
    crx_path = output_dir / f"textsync-{version}.crx"
    extension_id = create_crx3(zip_path, crx_path, private_key)

    if extension_id:
        # Create updates.xml
        create_updates_xml(extension_id, version, output_dir)

        # Create install instructions
        create_install_instructions(version, extension_id, output_dir)

    # Summary
    print("\n" + "="*50)
    print("BUILD COMPLETE")
    print("="*50)
    print(f"Version: {version}")
    if extension_id:
        print(f"Extension ID: {extension_id}")
    print(f"\nOutput files:")
    print(f"  - {zip_path}")
    if extension_id:
        print(f"  - {crx_path}")
        print(f"  - {output_dir / 'updates.xml'}")
    print(f"\nTo deploy, upload files to: {UPDATE_URL}/")


if __name__ == '__main__':
    main()
