import os
import zipfile
from pathlib import Path

def create_map_bundle(output_name="map_bundle"):
    """Create ZIP with all tiles from cache/world/ and cache/[country]/"""
    cache_dir = Path('cache')
    if not cache_dir.exists():
        print("Error: 'cache' directory not found")
        return

    zip_path = f"{output_name}.zip"
    total_files = 0
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for tile_dir in cache_dir.glob('*/*/*/*.png'):  # cache/[type]/z/x/y.png
            arcname = str(Path(*tile_dir.parts[2:]))  # Remove 'cache/[type]'
            zipf.write(tile_dir, arcname)
            total_files += 1
    
    print(f"\nCreated {zip_path} with {total_files} tiles")
    print(f"Size: {os.path.getsize(zip_path)/1024/1024:.2f} MB")

if __name__ == "__main__":
    create_map_bundle()