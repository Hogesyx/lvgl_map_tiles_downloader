LVGL Map Tiles Downloader
========================

A Python toolkit for downloading and packaging Google Maps tiles for LVGL-powered embedded devices.

Features
--------
- Downloads map tiles from Google Maps servers
- Organized cache structure (cache/world/ and cache/[country]/)
- Generates device-friendly ZIP bundles
- Optimized 8-bit PNGs for low-memory devices
- Supports all countries via ISO codes
- Multi-threaded downloads

Folder Structure
----------------
.
+-- cache/                   # Downloaded tiles storage
¦   +-- world/               # Global tiles (zoom 0-6)
¦   ¦   +-- 0/0/0.png
¦   ¦   +-- .../...
¦   +-- [country_code]/      # Country tiles (zoom 7-15)
¦       +-- 7/0/0.png
¦       +-- .../...
+-- bundle.zip               # Final output (z/x/y.png structure)
+-- country_bbox.json        # Country boundaries database
+-- map_downloader.py        # Download script
+-- map_bundle.py           # Bundle creator

Installation
------------
git clone https://github.com/yourusername/lvgl_map_tiles_downloader.git
cd lvgl_map_tiles_downloader
pip install -r requirements.txt

Usage
-----
# Download world + country tiles
python map_downloader.py --country SG

# Options:
# --country: Country code (e.g., US, JP) or name
# --threads: Parallel downloads (default: 4)
# --refresh: Cache duration in hours (default: 168)

# Create bundle
python map_bundle.py
# Generates bundle.zip with clean z/x/y.png structure

Requirements
------------
- Python 3.6+
- Pillow >=9.0.0
- Requests >=2.25.0
- pycountry >=20.7.3

License
-------
MIT License - See LICENSE for details.