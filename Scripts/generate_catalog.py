#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["lxml"]
# ///

import os
import json
import shutil
import hashlib
from lxml import etree

DATA_DIR = r"C:\AppSource\FiberArtData"
R2_BASE_URL = "https://storage.fiber-art.myshawn.com/"

def calculate_md5(file_path):
    """Calculate the MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

CATEGORIES = [
    {"folder": "Robots", "exts": (".urdf",), "type": "Robot"},
    {"folder": "Tracks", "exts": (".track",), "type": "Track"},
    {"folder": "Positioners", "exts": (".positioner",), "type": "Positioner"},
    {"folder": "Tools", "exts": (".jointless_tool", ".jointed_tool"), "type": "Tool"}
]

def main():
    catalog = {
        "version": "1.0",
        "models": []
    }
    
    for cat in CATEGORIES:
        source_dir = os.path.join(DATA_DIR, cat["folder"])
        zip_dir = os.path.join(DATA_DIR, f"{cat['folder']}_Zip")
        
        if not os.path.exists(source_dir):
            print(f"Directory {source_dir} not found. Skipping.")
            continue
            
        os.makedirs(zip_dir, exist_ok=True)
            
        for root_dir, dirs, files in os.walk(source_dir):
            for f in files:
                if f.endswith(cat["exts"]):
                    urdf_path = os.path.join(root_dir, f)
                    rel_urdf = os.path.relpath(urdf_path, DATA_DIR).replace('\\', '/')
                    
                    # Get the root directory of this model
                    model_dir = root_dir
                    while os.path.dirname(model_dir) != source_dir and model_dir != source_dir:
                        model_dir = os.path.dirname(model_dir)
                        
                    model_folder_name = os.path.basename(model_dir)
                    zip_filename = f"{model_folder_name}.zip"
                    
                    # Create the zip file containing the entire model folder
                    zip_base = os.path.join(zip_dir, model_folder_name)
                    print(f"Zipping {cat['folder']}/{model_folder_name}...")
                    shutil.make_archive(zip_base, 'zip', source_dir, model_folder_name)
                    
                    zip_url = f"{R2_BASE_URL}{cat['folder']}/{zip_filename}"
                    zip_path = f"{zip_base}.zip"
                    zip_hash = calculate_md5(zip_path)
                    
                    try:
                        tree = etree.parse(urdf_path)
                        root = tree.getroot()
                        
                        # Use the name attribute if available, else fallback to filename without extension
                        fallback_name = f
                        for ext in cat["exts"]:
                            if fallback_name.endswith(ext):
                                fallback_name = fallback_name[:-len(ext)]
                                break
                                
                        model_name = root.get('name', fallback_name)
                        
                        model_entry = {
                            "type": cat["type"],
                            "name": model_name,
                            "urdf": rel_urdf,
                            "uri": zip_url,
                            "hash": zip_hash
                        }
                        
                        brand = root.get('brand')
                        if brand is not None:
                            model_entry["brand"] = brand
                            
                        payload = root.get('payload')
                        if payload is not None:
                            try:
                                model_entry["payload"] = float(payload)
                            except ValueError:
                                model_entry["payload"] = payload
                                
                        reach = root.get('reach')
                        if reach is not None:
                            try:
                                model_entry["reach"] = float(reach)
                            except ValueError:
                                model_entry["reach"] = reach
                                
                        xml_type = root.get('type')
                        if xml_type is not None:
                            model_entry["type"] = xml_type
                            
                        catalog["models"].append(model_entry)
                    except Exception as e:
                        print(f"Error parsing {urdf_path}: {e}")
                    
    out_file = os.path.join(DATA_DIR, "catalog.json")
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        
    print(f"Generated catalog.json at {out_file} with {len(catalog['models'])} models.")

if __name__ == "__main__":
    main()
