import os
import time
import requests
from PIL import Image
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import json
import pycountry

# Load country bounding boxes
def load_country_bboxes():
    try:
        with open('country_bbox.json') as f:
            return json.load(f)
    except:
        return {'SG': {'min_lat': 1.15, 'max_lat': 1.47, 'min_lon': 103.5, 'max_lon': 104.2}}

COUNTRY_PRESETS = load_country_bboxes()
WORLD_BBOX = {'min_lat': -85, 'max_lat': 85, 'min_lon': -180, 'max_lon': 180}

def validate_country(country_input):
    try:
        country = pycountry.countries.get(alpha_2=country_input.upper()) or \
                 pycountry.countries.get(name=country_input)
        return country.alpha_2 if (country and country.alpha_2 in COUNTRY_PRESETS) else None
    except:
        return None

def download_tile(z, x, y, url_template, output_dir, refresh_hours, verbose=True):
    url = url_template.format(x=x, y=y, z=z)
    path = os.path.join('cache', output_dir, str(z), str(x))
    os.makedirs(path, exist_ok=True)
    file_path = os.path.join(path, f"{y}.png")
    
    if os.path.exists(file_path):
        file_age_hours = (time.time() - os.path.getmtime(file_path)) / 3600
        if file_age_hours < refresh_hours:
            if verbose: print(f"[CACHE] z{z} {x}/{y}")
            return False
    
    try:
        if verbose: print(f"[GET] z{z} {x}/{y}")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        img = Image.open(file_path)
        img = img.convert('P', palette=Image.ADAPTIVE, colors=128)
        img.save(file_path, optimize=True, compress_level=9)
        return True
    except Exception as e:
        if verbose: print(f"[FAIL] z{z} {x}/{y}: {str(e)}")
        return False

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
    return min(x_min, max_tile), min(x_max, max_tile), min(y_min, max_tile), min(y_max, max_tile)

def download_area(bbox, url_template, output_dir, min_zoom, max_zoom, refresh_hours, max_workers, verbose):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for z in range(min_zoom, max_zoom + 1):
            x_min, x_max, y_min, y_max = get_tile_range(bbox, z)
            if verbose: print(f"z{z}: {x_max-x_min+1}x{y_max-y_min+1} tiles")
            
            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    futures.append(executor.submit(
                        download_tile, z, x, y, url_template, output_dir, refresh_hours, verbose
                    ))
        
        return sum(future.result() for future in as_completed(futures))

def main():
    parser = argparse.ArgumentParser(description='Download map tiles for LVGL')
    parser.add_argument('--country', help='Country code or name')
    parser.add_argument('--refresh', type=int, default=168, help='Refresh threshold in hours')
    parser.add_argument('--threads', type=int, default=4, help='Max concurrent downloads')
    parser.add_argument('--quiet', action='store_true', help='Reduce output verbosity')
    args = parser.parse_args()

    os.makedirs('cache', exist_ok=True)
    url_template = "https://mt0.google.com/vt?lyrs=p&x={x}&s=&y={y}&z={z}"
    verbose = not args.quiet

    # Download world tiles (0-6)
    if verbose: print("Downloading world tiles (zoom 0-6)...")
    downloaded = download_area(
        WORLD_BBOX, url_template, "world",
        0, 6, args.refresh, args.threads, verbose
    )
    if verbose: print(f"Downloaded {downloaded} world tiles")

    # Download country tiles
    if args.country:
        country_code = validate_country(args.country)
        if country_code:
            if verbose: print(f"\nDownloading {country_code} tiles (zoom 7-15)...")
            downloaded = download_area(
                COUNTRY_PRESETS[country_code], url_template, country_code.lower(),
                7, 15, args.refresh, args.threads, verbose
            )
            if verbose: print(f"Downloaded {downloaded} {country_code} tiles")
        else:
            print(f"Error: Country '{args.country}' not supported")

if __name__ == "__main__":
    main()