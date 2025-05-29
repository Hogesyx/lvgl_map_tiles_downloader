import os
import time
import requests
from PIL import Image
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import io
import json

# Constants and Configuration
WORLD_BBOX = {'min_lat': -85, 'max_lat': 85, 'min_lon': -180, 'max_lon': 180}
DEFAULT_URL = "https://mt0.google.com/vt?lyrs=p&x={x}&s=&y={y}&z={z}"

def print_legal_disclaimer():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                             LEGAL DISCLAIMER                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ THIS TOOL IS FOR PERSONAL AND EDUCATIONAL USE ONLY                           ║
║                                                                              ║
║ Google Maps tiles are subject to Terms of Service:                           ║
║ https://www.google.com/intl/en_us/help/terms_maps/                           ║
║                                                                              ║
║ By using this tool you agree to:                                             ║
║ - Not mass-download or redistribute tiles                                    ║
║ - Comply with Google's usage limits                                          ║
║ - Use tiles only with proper Google attribution if displayed                 ║
║                                                                              ║
║ For commercial use, obtain a Google Maps API license:                        ║
║ https://developers.google.com/maps/documentation                             ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

class TileProgress:
    def __init__(self, total_tiles, country_code=None):
        self.start_time = time.time()
        self.total_tiles = total_tiles
        self.completed = 0
        self.zone_totals = {}
        self.zone_counts = {}
        self.country_code = country_code
        
    def init_zone(self, z, zone_total):
        self.zone_totals[z] = zone_total
        self.zone_counts[z] = 0
        
    def update(self, z, x, y, status):
        self.completed += 1
        self.zone_counts[z] += 1
        
        elapsed = time.time() - self.start_time
        rate = self.completed / elapsed if elapsed > 0 else 0
        eta = (self.total_tiles - self.completed) / rate if rate > 0 else 0
        
        country_prefix = f"{self.country_code} " if self.country_code else ""
        print(
            f"[{status}] z{z}/{x}/{y} | "
            f"{country_prefix}Zone: {self.zone_counts[z]}/{self.zone_totals[z]} | "
            f"Overall: {self.completed}/{self.total_tiles} | "
            f"{rate:.1f} tiles/s | ETA: {eta:.1f}s"
        )

def load_country_bboxes():
    try:
        with open('country_bbox.json') as f:
            return json.load(f)
    except:
        return {'SG': {'min_lat': 1.15, 'max_lat': 1.47, 'min_lon': 103.5, 'max_lon': 104.2}}

def get_country_bbox(country_code):
    country_code = country_code.upper()
    presets = load_country_bboxes()
    return presets.get(country_code)

def download_tile(z, x, y, url_template, output_dir, max_retries=3, initial_delay=1):
    url = url_template.format(x=x, y=y, z=z)
    path = os.path.join('cache', output_dir, str(z), str(x))
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{y}.png")
    
    # Check existing file
    if os.path.exists(file_path):
        try:
            with Image.open(file_path) as img:
                img.verify()
            return {'status': 'CACHE', 'z': z, 'x': x, 'y': y}
        except:
            os.remove(file_path)
    
    # Download with retries
    for attempt in range(max_retries):
        try:
            time.sleep(initial_delay * (2 ** attempt))  # Exponential backoff
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            
            # Validate and save image
            img_data = io.BytesIO(response.content)
            with Image.open(img_data) as img:
                img = img.convert('P', palette=Image.ADAPTIVE, colors=128)
                img.save(file_path, optimize=True, compress_level=9)
            return {'status': 'SUCCESS', 'z': z, 'x': x, 'y': y}
            
        except Exception as e:
            if attempt == max_retries - 1:
                return {'status': 'FAILED', 'z': z, 'x': x, 'y': y, 'error': str(e)}
    
    return {'status': 'FAILED', 'z': z, 'x': x, 'y': y, 'error': 'Max retries exceeded'}

def lat_lon_to_tile(lat, lon, zoom):
    lat_rad = math.radians(lat)
    n = 2.0 ** zoom
    xtile = int((lon + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def get_tile_range(bbox, zoom):
    x_min, y_max = lat_lon_to_tile(bbox['max_lat'], bbox['min_lon'], zoom)
    x_max, y_min = lat_lon_to_tile(bbox['min_lat'], bbox['max_lon'], zoom)
    x_min, x_max = sorted([max(0, x) for x in [x_min, x_max]])
    y_min, y_max = sorted([max(0, y) for y in [y_min, y_max]])
    max_tile = 2**zoom - 1
    return (
        min(x_min, max_tile),
        min(x_max, max_tile),
        min(y_min, max_tile),
        min(y_max, max_tile)
    )

def download_and_report(z, x, y, url_template, output_dir, progress):
    result = download_tile(z, x, y, url_template, output_dir)
    progress.update(z, x, y, result['status'])
    return result

def download_area(bbox, url_template, output_dir, min_zoom, max_zoom, max_workers=4, country_code=None):
    # Calculate totals
    total_tiles = 0
    zone_totals = {}
    for z in range(min_zoom, max_zoom + 1):
        x_min, x_max, y_min, y_max = get_tile_range(bbox, z)
        zone_total = (x_max - x_min + 1) * (y_max - y_min + 1)
        zone_totals[z] = zone_total
        total_tiles += zone_total
    
    progress = TileProgress(total_tiles, country_code)
    for z in zone_totals:
        progress.init_zone(z, zone_totals[z])
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for z in range(min_zoom, max_zoom + 1):
            x_min, x_max, y_min, y_max = get_tile_range(bbox, z)
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    future = executor.submit(
                        lambda z=z, x=x, y=y: download_and_report(z, x, y, url_template, output_dir, progress)
                    )
                    futures.append(future)
        
        # Wait for completion
        results = []
        for future in as_completed(futures):
            results.append(future.result())
    
    # Final report
    success = sum(1 for r in results if r['status'] == 'SUCCESS')
    cached = sum(1 for r in results if r['status'] == 'CACHE')
    failed = sum(1 for r in results if r['status'] == 'FAILED')
    
    print("\n=== Download Summary ===")
    if country_code:
        print(f"Country: {country_code}")
    print(f"Total tiles: {total_tiles}")
    print(f"New downloads: {success}")
    print(f"From cache: {cached}")
    print(f"Failed: {failed}")
    print(f"Total time: {time.time() - progress.start_time:.2f} seconds")

def main():
    print_legal_disclaimer()
    parser = argparse.ArgumentParser(description='Map Tile Downloader for LVGL')
    parser.add_argument('--country', help='Country code (e.g. SG, US)')
    parser.add_argument('--minzoom', type=int, default=0, help='Minimum zoom level (0-15)')
    parser.add_argument('--maxzoom', type=int, default=15, help='Maximum zoom level (0-15)')
    parser.add_argument('--threads', type=int, default=4, help='Number of parallel downloads')
    parser.add_argument('--url', default=DEFAULT_URL, help='Tile server URL template')
    args = parser.parse_args()

    os.makedirs('cache', exist_ok=True)
    
    # Download world tiles (0-6)
    print("Downloading world tiles (zoom 0-6)...")
    download_area(
        WORLD_BBOX, args.url, "world",
        max(0, args.minzoom), min(6, args.maxzoom),
        args.threads
    )
    
    # Download country tiles if specified
    if args.country:
        country_bbox = get_country_bbox(args.country)
        if country_bbox:
            print(f"\nDownloading {args.country} tiles (zoom 7-15)...")
            download_area(
                country_bbox, args.url, args.country.lower(),
                max(7, args.minzoom), min(15, args.maxzoom),
                args.threads, 
                country_code=args.country
            )
        else:
            print(f"Error: No bounding box found for country '{args.country}'")

if __name__ == "__main__":
    main()