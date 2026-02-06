"""
Download GeoIP sources defined in sources.yaml
"""

import os
import sys

import requests
import yaml


def download_file(url, dest_path):
    if not url:
        print(f"  Skipping (no URL): {dest_path}")
        return -1

    print(f"  Downloading: {url}")
    try:
        resp = requests.get(url, stream=True, timeout=300)

        if resp.status_code != 200:
            print(f"  Failed: HTTP {resp.status_code}")
            return resp.status_code

        with open(dest_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  Saved: {dest_path}")
        return 200
    except Exception as e:
        print(f"  Error: {e}")
        return -1


def main():
    if len(sys.argv) != 4:
        print("Usage: download.py <sources.yaml> <ipv4|ipv6> <output_dir>")
        sys.exit(1)

    sources_file = sys.argv[1]
    ip_version = sys.argv[2]
    output_dir = sys.argv[3]

    with open(sources_file) as f:
        sources = yaml.safe_load(f)

    os.makedirs(output_dir, exist_ok=True)

    failed = []

    for section in ('latlong', 'country'):
        print(f"\nDownloading {ip_version} {section} sources...")
        for name, info in sources.get(section, {}).items():
            url = info.get(ip_version, '')
            ext = 'csv' if info.get('format') == 'decimal_csv' else 'tsv'
            dest = os.path.join(output_dir, f"{name}.{ext}")
            status = download_file(url, dest)
            if status != 200:
                failed.append((name, status))

    if failed:
        print("\nFailed downloads:")
        for name, status in failed:
            print(f"  {name}: {status}")
        sys.exit(1)

    print("\nDownload complete!")


if __name__ == '__main__':
    main()
