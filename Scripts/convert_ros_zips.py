#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["lxml", "xacro", "rospkg"]
# ///

import os
import sys
import re
import math
import shutil
import zipfile
import glob
import json
import types
from lxml import etree

DATA_DIR = r"C:\AppSource\FiberArtData"
ROBOTS_DIR = os.path.join(DATA_DIR, "Robots")
ZIPS_DIR = os.path.join(DATA_DIR, "ros-robots")
OUT_ZIPS_DIR = os.path.join(DATA_DIR, "Robots_Zip")
TEMP_DIR = os.path.join(DATA_DIR, "temp_conversion")

# Exact technical specifications of all new robots
ROBOT_SPECS = {
    # ABB
    "CRB15000_12_127": {"brand": "ABB", "payload": 12.0, "reach": 1.27},
    "CRB15000_5_95": {"brand": "ABB", "payload": 5.0, "reach": 0.95},
    "IRB1200_5_90": {"brand": "ABB", "payload": 5.0, "reach": 0.90},
    "IRB1200_7_70": {"brand": "ABB", "payload": 7.0, "reach": 0.70},
    "IRB120_3_58": {"brand": "ABB", "payload": 3.0, "reach": 0.58},
    "IRB120T_3_58": {"brand": "ABB", "payload": 3.0, "reach": 0.58},
    "IRB1600_10_145": {"brand": "ABB", "payload": 10.0, "reach": 1.45},
    "IRB1600_6_12": {"brand": "ABB", "payload": 6.0, "reach": 1.20},
    "IRB1600_8_145": {"brand": "ABB", "payload": 8.0, "reach": 1.45},
    "IRB2400_12_155": {"brand": "ABB", "payload": 12.0, "reach": 1.55},
    "IRB2400": {"brand": "ABB", "payload": 12.0, "reach": 1.55},
    "IRB2600_12_165": {"brand": "ABB", "payload": 12.0, "reach": 1.65},
    "IRB2600_12_185": {"brand": "ABB", "payload": 12.0, "reach": 1.85},
    "IRB4400L_30_243": {"brand": "ABB", "payload": 30.0, "reach": 2.43},
    "IRB4600_20_250": {"brand": "ABB", "payload": 20.0, "reach": 2.50},
    "IRB4600_40_255": {"brand": "ABB", "payload": 40.0, "reach": 2.55},
    "IRB4600_60_205": {"brand": "ABB", "payload": 60.0, "reach": 2.05},
    "IRB52_7_120": {"brand": "ABB", "payload": 7.0, "reach": 1.20},
    "IRB52_7_145": {"brand": "ABB", "payload": 7.0, "reach": 1.45},
    "IRB5400": {"brand": "ABB", "payload": 15.0, "reach": 1.62},
    "IRB6600_225_255": {"brand": "ABB", "payload": 225.0, "reach": 2.55},
    "IRB6640": {"brand": "ABB", "payload": 180.0, "reach": 2.55},
    "IRB6640_185_280": {"brand": "ABB", "payload": 185.0, "reach": 2.80},
    "IRB6650S_125_350": {"brand": "ABB", "payload": 125.0, "reach": 3.50},
    "IRB6650S_90_390": {"brand": "ABB", "payload": 90.0, "reach": 3.90},
    "IRB6700_200_260": {"brand": "ABB", "payload": 200.0, "reach": 2.60},
    "IRB6700_235_265": {"brand": "ABB", "payload": 235.0, "reach": 2.65},
    "IRB7600_150_350": {"brand": "ABB", "payload": 150.0, "reach": 3.50},
    # Fanuc
    "CR35IA": {"brand": "FANUC", "payload": 35.0, "reach": 1.813},
    "CR7IA": {"brand": "FANUC", "payload": 7.0, "reach": 0.717},
    "CR7IAL": {"brand": "FANUC", "payload": 7.0, "reach": 0.911},
    "CRX10IAL": {"brand": "FANUC", "payload": 10.0, "reach": 1.418},
    "LRMATE200I": {"brand": "FANUC", "payload": 3.0, "reach": 0.56},
    "LRMATE200IB": {"brand": "FANUC", "payload": 5.0, "reach": 0.70},
    "LRMATE200IB3L": {"brand": "FANUC", "payload": 3.0, "reach": 0.83},
    "LRMATE200IC": {"brand": "FANUC", "payload": 5.0, "reach": 0.704},
    "LRMATE200IC5F": {"brand": "FANUC", "payload": 5.0, "reach": 0.704},
    "LRMATE200IC5H": {"brand": "FANUC", "payload": 5.0, "reach": 0.704},
    "LRMATE200IC5HS": {"brand": "FANUC", "payload": 5.0, "reach": 0.704},
    "M10IA": {"brand": "FANUC", "payload": 10.0, "reach": 1.42},
    "M10IA7L": {"brand": "FANUC", "payload": 7.0, "reach": 1.633},
    "M16IB": {"brand": "FANUC", "payload": 20.0, "reach": 1.667},
    "M16IB20": {"brand": "FANUC", "payload": 20.0, "reach": 1.667},
    "M20IA": {"brand": "FANUC", "payload": 20.0, "reach": 1.811},
    "M20IA10L": {"brand": "FANUC", "payload": 10.0, "reach": 2.009},
    "M20IAB": {"brand": "FANUC", "payload": 20.0, "reach": 1.811},
    "M430IA2F": {"brand": "FANUC", "payload": 2.0, "reach": 0.90},
    "M430IAP2F": {"brand": "FANUC", "payload": 2.0, "reach": 0.90},
    "M710IC50": {"brand": "FANUC", "payload": 50.0, "reach": 2.05},
    "M710IC70": {"brand": "FANUC", "payload": 70.0, "reach": 2.05},
    "M900IA350": {"brand": "FANUC", "payload": 350.0, "reach": 3.0},
    "M900IA400": {"brand": "FANUC", "payload": 400.0, "reach": 3.0},
    "M900IA600": {"brand": "FANUC", "payload": 600.0, "reach": 2.83},
    "R1000IA80F": {"brand": "FANUC", "payload": 80.0, "reach": 2.23},
    "R2000IA125F": {"brand": "FANUC", "payload": 125.0, "reach": 2.655},
    "R2000IA165F": {"brand": "FANUC", "payload": 165.0, "reach": 2.655},
    "R2000IA200F": {"brand": "FANUC", "payload": 200.0, "reach": 2.655},
    "R2000IB125F": {"brand": "FANUC", "payload": 125.0, "reach": 2.655},
    "R2000IB165F": {"brand": "FANUC", "payload": 165.0, "reach": 2.655},
    "R2000IB175L": {"brand": "FANUC", "payload": 175.0, "reach": 2.852},
    "R2000IB185F": {"brand": "FANUC", "payload": 185.0, "reach": 2.655},
    "R2000IB210F": {"brand": "FANUC", "payload": 210.0, "reach": 2.655},
    "R2000IC125F": {"brand": "FANUC", "payload": 125.0, "reach": 2.655},
    "R2000IC165F": {"brand": "FANUC", "payload": 165.0, "reach": 2.655},
    "R2000IC210F": {"brand": "FANUC", "payload": 210.0, "reach": 2.655},
    "R2000IC270F": {"brand": "FANUC", "payload": 270.0, "reach": 2.655},
    # Motoman
    "AR2010": {"brand": "MOTOMAN", "payload": 12.0, "reach": 2.01},
    "ES165": {"brand": "MOTOMAN", "payload": 165.0, "reach": 2.651},
    "ES200_120": {"brand": "MOTOMAN", "payload": 120.0, "reach": 3.14},
    "GP110": {"brand": "MOTOMAN", "payload": 110.0, "reach": 2.235},
    "GP12": {"brand": "MOTOMAN", "payload": 12.0, "reach": 1.44},
    "GP165R": {"brand": "MOTOMAN", "payload": 165.0, "reach": 3.14},
    "GP180": {"brand": "MOTOMAN", "payload": 180.0, "reach": 2.702},
    "GP180_120": {"brand": "MOTOMAN", "payload": 120.0, "reach": 3.058},
    "GP200R": {"brand": "MOTOMAN", "payload": 200.0, "reach": 3.14},
    "GP25": {"brand": "MOTOMAN", "payload": 25.0, "reach": 1.73},
    "GP50": {"brand": "MOTOMAN", "payload": 50.0, "reach": 2.061},
    "GP8": {"brand": "MOTOMAN", "payload": 8.0, "reach": 0.727},
    "HC10": {"brand": "MOTOMAN", "payload": 10.0, "reach": 1.20},
    "HC10DT": {"brand": "MOTOMAN", "payload": 10.0, "reach": 1.20},
    "H2400": {"brand": "MOTOMAN", "payload": 150.0, "reach": 2.40},
    "MH12": {"brand": "MOTOMAN", "payload": 12.0, "reach": 1.44},
    "MH180": {"brand": "MOTOMAN", "payload": 180.0, "reach": 2.702},
    "MH180_120": {"brand": "MOTOMAN", "payload": 120.0, "reach": 3.058},
    "MH200": {"brand": "MOTOMAN", "payload": 200.0, "reach": 2.659},
    "MH24": {"brand": "MOTOMAN", "payload": 24.0, "reach": 1.73},
    "MH5": {"brand": "MOTOMAN", "payload": 5.0, "reach": 0.706},
    "MH50": {"brand": "MOTOMAN", "payload": 50.0, "reach": 2.061},
    "MH5L": {"brand": "MOTOMAN", "payload": 5.0, "reach": 0.895},
    "MH6": {"brand": "MOTOMAN", "payload": 6.0, "reach": 1.422},
    "MH60": {"brand": "MOTOMAN", "payload": 60.0, "reach": 2.236},
    "MH80": {"brand": "MOTOMAN", "payload": 80.0, "reach": 2.061},
    "SDA10F": {"brand": "MOTOMAN", "payload": 10.0, "reach": 0.72},
    "SDA5F": {"brand": "MOTOMAN", "payload": 5.0, "reach": 0.56},
    "SIA10D": {"brand": "MOTOMAN", "payload": 10.0, "reach": 1.20},
    "SIA20D": {"brand": "MOTOMAN", "payload": 20.0, "reach": 1.30},
    "SIA5D": {"brand": "MOTOMAN", "payload": 5.0, "reach": 0.72},
    "UP20": {"brand": "MOTOMAN", "payload": 20.0, "reach": 1.658},
    "UP50": {"brand": "MOTOMAN", "payload": 50.0, "reach": 2.061},
    "ES165RD": {"brand": "MOTOMAN", "payload": 165.0, "reach": 3.14},
    "ES200RD": {"brand": "MOTOMAN", "payload": 200.0, "reach": 3.14},
    "GP180_120RD": {"brand": "MOTOMAN", "payload": 120.0, "reach": 3.058},
    "GP180RD": {"brand": "MOTOMAN", "payload": 180.0, "reach": 3.14},
    "GP200RD": {"brand": "MOTOMAN", "payload": 200.0, "reach": 3.14},
    "MH180_120RD": {"brand": "MOTOMAN", "payload": 120.0, "reach": 3.058},
    "MH180RD": {"brand": "MOTOMAN", "payload": 180.0, "reach": 3.14},
    "MH200RD": {"brand": "MOTOMAN", "payload": 200.0, "reach": 3.14},
    # Staubli
    "RX160": {"brand": "STAUBLI", "payload": 20.0, "reach": 1.60},
    "RX160L": {"brand": "STAUBLI", "payload": 14.0, "reach": 2.01},
    # Universal Robots
    "UR3": {"brand": "UR", "payload": 3.0, "reach": 0.50},
    "UR3E": {"brand": "UR", "payload": 3.0, "reach": 0.50},
    "UR5": {"brand": "UR", "payload": 5.0, "reach": 0.85},
    "UR5E": {"brand": "UR", "payload": 5.0, "reach": 0.85},
    "UR10": {"brand": "UR", "payload": 10.0, "reach": 1.30},
    "UR10E": {"brand": "UR", "payload": 10.0, "reach": 1.30},
    "UR12E": {"brand": "UR", "payload": 12.5, "reach": 1.30},
    "UR16E": {"brand": "UR", "payload": 16.0, "reach": 0.90},
    "UR20": {"brand": "UR", "payload": 20.0, "reach": 1.75},
    "UR30": {"brand": "UR", "payload": 30.0, "reach": 1.30},
    # KUKA
    "KR10R1100SIXX": {"brand": "KUKA", "payload": 10.0, "reach": 1.101},
    "KR10R1420": {"brand": "KUKA", "payload": 10.0, "reach": 1.42},
    "KR10R900_2": {"brand": "KUKA", "payload": 10.0, "reach": 0.901},
    "KR120R2500PRO": {"brand": "KUKA", "payload": 120.0, "reach": 2.496},
    "KR150_2": {"brand": "KUKA", "payload": 150.0, "reach": 2.70},
    "KR150R3100_2": {"brand": "KUKA", "payload": 150.0, "reach": 3.095},
    "KR16_2": {"brand": "KUKA", "payload": 16.0, "reach": 1.611},
    "KR210L150": {"brand": "KUKA", "payload": 150.0, "reach": 3.10},
    "KR3R540": {"brand": "KUKA", "payload": 3.0, "reach": 0.54},
    "KR5_ARC": {"brand": "KUKA", "payload": 5.0, "reach": 1.611},
    "KR6R700SIXX": {"brand": "KUKA", "payload": 6.0, "reach": 0.706},
    "KR6R900_2": {"brand": "KUKA", "payload": 6.0, "reach": 0.901},
    "KR6R900SIXX": {"brand": "KUKA", "payload": 6.0, "reach": 0.901},
    "LBR_IIWA_14_R820": {"brand": "KUKA", "payload": 14.0, "reach": 0.82}
}

def clean_temp_dir():
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

def strip_namespaces(node):
    if type(node.tag) is str and '}' in node.tag:
        node.tag = node.tag.split('}', 1)[1]
    for child in node:
        strip_namespaces(child)

def find_file_in_dir(filename, search_dir, is_dir=False):
    """Finds a file or directory recursively in search_dir, matches basename case-insensitively."""
    fn_lower = filename.lower()
    for r, d, files in os.walk(search_dir):
        items = d if is_dir else files
        for item in items:
            if item.lower() == fn_lower:
                return os.path.join(r, item)
    return None

def copy_mesh_file(package_filename, search_root, target_visual_dir, target_collision_dir, is_visual=True):
    """Copies mesh files from search_root to the target dir, returns the new relative path."""
    basename = os.path.basename(package_filename)
    dest_dir = target_visual_dir if is_visual else target_collision_dir
    dest_path = os.path.join(dest_dir, basename)
    
    # Try exact package path resolution first
    found_path = None
    if package_filename.startswith("package://"):
        clean_url = package_filename.replace("package://", "")
        parts = clean_url.split("/", 1)
        if len(parts) == 2:
            pkg_name, rest_path = parts
            pkg_dir = find_file_in_dir(pkg_name, search_root, is_dir=True)
            if pkg_dir:
                rest_path_os = rest_path.replace("/", os.sep).replace("\\", os.sep)
                candidate_path = os.path.join(pkg_dir, rest_path_os)
                if os.path.exists(candidate_path):
                    found_path = candidate_path
                    
    # Fallback to recursive search if exact resolution failed
    if not found_path:
        found_path = find_file_in_dir(basename, search_root)
        
    if found_path and os.path.exists(found_path):
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(found_path, dest_path)
        # Also copy associated DAE textures if it is a dae
        if basename.lower().endswith('.dae'):
            # Look for texture images in the same folder as found_path
            src_dir = os.path.dirname(found_path)
            for f in os.listdir(src_dir):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
                    shutil.copy2(os.path.join(src_dir, f), os.path.join(dest_dir, f))
        
        rel_prefix = "visual" if is_visual else "collision"
        return f"{rel_prefix}/{basename}"
    else:
        print(f"Warning: mesh file not found: {basename}")
        return None

def extract_colors_from_xml(filepath):
    """Parses properties and macro colors from a xacro file."""
    colors = {}
    if not os.path.exists(filepath):
        return colors
        
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Basic arithmetic evaluation
        def eval_fraction(match):
            expr = match.group(1).replace(' ', '')
            try:
                if '/' in expr:
                    num, den = expr.split('/')
                    return str(round(float(num) / float(den), 6))
            except:
                pass
            return match.group(1)
            
        content = re.sub(r'\$\{([^}]+)\}', eval_fraction, content)
        
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.fromstring(content.encode('utf-8'), parser)
        
        # Look for properties in a namespace-agnostic way
        props = tree.xpath("//*[local-name()='property']")
        for prop in props:
            name = prop.get('name')
            val = prop.get('value')
            if name and val:
                if name.startswith('colour_'):
                    name = name.replace('colour_', '')
                colors[name] = val
    except Exception as e:
        print(f"Error parsing color file {filepath}: {e}")
        
    return colors

def get_all_colors_in_extracted_dir(extracted_dir):
    """Finds all colour/material xacro files and compiles a colors dictionary."""
    colors = {}
    for r, d, files in os.walk(extracted_dir):
        for f in files:
            if f.endswith('.xacro') and ('colour' in f.lower() or 'material' in f.lower()):
                colors.update(extract_colors_from_xml(os.path.join(r, f)))
    return colors

def convert_standard_macro(filepath, zip_root_dir, colors):
    """Processes a KUKA/ABB/Fanuc/Staubli/Motoman *_macro.xacro file."""
    print(f"Converting standard macro: {os.path.basename(filepath)}")
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Replace ${prefix} with empty string
    content = content.replace('${prefix}', '')
    
    # We do NOT run regex to convert ${radians(xxx)} to keep readability!
    
    parser = etree.XMLParser(remove_blank_text=True)
    try:
        tree = etree.fromstring(content.encode('utf-8'), parser)
    except Exception as e:
        print(f"Error parsing xml {filepath}: {e}")
        return None
        
    import copy
    macro_elems = tree.xpath("//*[local-name()='macro']")
    if not macro_elems:
        print(f"No macro found in {filepath}")
        return None
            
    macro_elem = macro_elems[0]
    raw_name = macro_elem.get('name', 'unknown')
    
    # Clean up origin name: e.g. staubli_rx160 -> RX160, abb_irb120 -> IRB120
    origin_name = raw_name.upper()
    for prefix in ['KUKA_', 'ABB_', 'FANUC_', 'STAUBLI_', 'MOTOMAN_']:
        if origin_name.startswith(prefix):
            origin_name = origin_name[len(prefix):]
            
    origin_name = origin_name.upper()
    
    # Query ROBOT_SPECS or guess brand using origin_name
    spec = ROBOT_SPECS.get(origin_name, {"brand": "Unknown", "payload": 0.0, "reach": 0.0})
    brand = spec["brand"]
    if brand == "Unknown":
        if origin_name.startswith("IRB") or origin_name.startswith("CRB"):
            brand = "ABB"
        elif origin_name.startswith("GP") or origin_name.startswith("AR") or origin_name.startswith("MH") or origin_name.startswith("HC") or origin_name.startswith("SDA") or origin_name.startswith("SIA") or origin_name.startswith("UP") or origin_name == "MOTOMINI" or "CSDA10F" in origin_name or "MA2010" in origin_name or "MOTOPOS" in origin_name or "MPX1950" in origin_name or "MS210" in origin_name or "TORSO" in origin_name:
            brand = "MOTOMAN"
        elif origin_name.startswith("RX"):
            brand = "STAUBLI"
        elif origin_name.startswith("M-") or origin_name.startswith("R-") or origin_name.startswith("LRMATE") or origin_name.startswith("CR") or origin_name.startswith("M10") or origin_name.startswith("M16") or origin_name.startswith("M20") or origin_name.startswith("M430") or origin_name.startswith("M6") or origin_name.startswith("M710") or origin_name.startswith("M900") or "R2000IC" in origin_name:
            brand = "FANUC"
        elif origin_name.startswith("KR") or origin_name.startswith("LBR"):
            brand = "KUKA"
        else:
            brand = "Custom"
            
    brand_prefix = brand.upper().replace(" ", "_") + "_"
    robot_name = brand_prefix + origin_name
    
    robot_out_dir = os.path.join(ROBOTS_DIR, robot_name)
    vis_out_dir = os.path.join(robot_out_dir, "visual")
    col_out_dir = os.path.join(robot_out_dir, "collision")
    
    new_root = etree.Element('robot', name=robot_name)
    
    # Copy all children of macro
    for child in macro_elem:
        if type(child.tag) is str and child.tag.endswith('include'):
            continue
        new_root.append(copy.deepcopy(child))
        
    strip_namespaces(new_root)
    
    used_materials = set()
    for elem in new_root.iter():
        if isinstance(elem.tag, str):
            # Convert material_name tags to standard material tags
            if elem.tag.startswith('material_'):
                mat_name = elem.tag.replace('material_', '')
                elem.tag = 'material'
                elem.set('name', mat_name)
                
            if elem.tag == 'material':
                name = elem.get('name')
                if name:
                    used_materials.add(name)
                    
        # Process mesh filenames
        if elem.tag == 'mesh' and 'filename' in elem.attrib:
            filename = elem.attrib['filename']
            if filename.startswith('package://'):
                p = elem.getparent()
                while p is not None and p.tag not in ['visual', 'collision']:
                    p = p.getparent()
                    
                is_visual = True
                if p is not None and p.tag == 'collision':
                    is_visual = False
                    
                new_filename = copy_mesh_file(filename, zip_root_dir, vis_out_dir, col_out_dir, is_visual)
                if new_filename:
                    elem.attrib['filename'] = new_filename
                    
    # Insert materials definitions at the top
    insert_idx = 0
    for mat_name in sorted(used_materials):
        color_val = colors.get(mat_name)
        if not color_val:
            # try with brand prefix or lower
            for k, v in colors.items():
                if k.lower() == mat_name.lower() or k.lower().endswith(mat_name.lower()):
                    color_val = v
                    break
        if not color_val:
            color_val = "0.7 0.7 0.7 1.0" # Default grey
            
        mat_elem = etree.Element('material', name=mat_name)
        etree.SubElement(mat_elem, 'color', rgba=color_val)
        mat_elem.tail = '\n  '
        new_root.insert(insert_idx, mat_elem)
        insert_idx += 1
        
    if insert_idx > 0:
        new_root[insert_idx - 1].tail = '\n\n  '
        
    os.makedirs(robot_out_dir, exist_ok=True)
    out_urdf_path = os.path.join(robot_out_dir, f"{robot_name}.urdf")
    urdf_content = etree.tostring(new_root, encoding='utf-8', xml_declaration=True, pretty_print=True).decode('utf-8')
    urdf_content = re.sub(r'\s+xmlns:xacro="[^"]*"', '', urdf_content)
    with open(out_urdf_path, 'w', encoding='utf-8') as f:
        f.write(urdf_content)
    print(f"Generated {out_urdf_path}")
    return robot_name

def convert_ur_robots(extracted_dir):
    """Compiles and converts UR robots using the official xacro parser and our ament_index_python mock."""
    print("Compiling and converting Universal Robots (UR)...")
    
    # 1. Mock ament_index_python
    sys.modules['ament_index_python'] = types.ModuleType('ament_index_python')
    pkg_module = types.ModuleType('packages')
    # Point get_package_share_directory to the extracted ur_description folder
    ur_desc_dir = find_file_in_dir('ur_description', extracted_dir, is_dir=True)
    if not ur_desc_dir:
        print("Error: ur_description folder not found in extracted UR zip!")
        return []
        
    pkg_module.get_package_share_directory = lambda name: ur_desc_dir
    sys.modules['ament_index_python.packages'] = pkg_module
    
    import xacro
    
    urdf_dir = os.path.join(ur_desc_dir, "urdf")
    # All top-level ur*.xacro files in ur_description/urdf
    xacro_files = glob.glob(os.path.join(urdf_dir, "ur*.xacro"))
    
    converted_names = []
    
    for xfile in xacro_files:
        basename = os.path.basename(xfile)
        # Skip inc/ and macro files
        if basename.endswith('_macro.xacro') or basename == 'ur.xacro':
            continue
            
        robot_name = "UR_" + basename.replace('.xacro', '').upper()
        print(f"Processing UR model: {robot_name}")
        
        try:
            doc = xacro.process_file(xfile)
            urdf_str = doc.toprettyxml(indent='  ')
            
            # Parse compiled URDF with lxml
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.fromstring(urdf_str.encode('utf-8'), parser)
            
            robot_out_dir = os.path.join(ROBOTS_DIR, robot_name)
            vis_out_dir = os.path.join(robot_out_dir, "visual")
            col_out_dir = os.path.join(robot_out_dir, "collision")
            
            strip_namespaces(tree)
            
            for elem in tree.iter():
                if elem.tag == 'mesh' and 'filename' in elem.attrib:
                    filename = elem.attrib['filename']
                    if filename.startswith('package://'):
                        p = elem.getparent()
                        while p is not None and p.tag not in ['visual', 'collision']:
                            p = p.getparent()
                            
                        is_visual = True
                        if p is not None and p.tag == 'collision':
                            is_visual = False
                            
                        new_filename = copy_mesh_file(filename, ur_desc_dir, vis_out_dir, col_out_dir, is_visual)
                        if new_filename:
                            elem.attrib['filename'] = new_filename
                            
            # Rename robot name to match folder
            tree.set('name', robot_name)
            
            os.makedirs(robot_out_dir, exist_ok=True)
            out_urdf_path = os.path.join(robot_out_dir, f"{robot_name}.urdf")
            urdf_content = etree.tostring(tree, encoding='utf-8', xml_declaration=True, pretty_print=True).decode('utf-8')
            urdf_content = re.sub(r'\s+xmlns:xacro="[^"]*"', '', urdf_content)
            with open(out_urdf_path, 'w', encoding='utf-8') as f:
                f.write(urdf_content)
            print(f"Generated {out_urdf_path}")
            converted_names.append(robot_name)
        except Exception as e:
            print(f"Error compiling UR xacro {xfile}: {e}")
            
    return converted_names

def main():
    clean_temp_dir()
    os.makedirs(ROBOTS_DIR, exist_ok=True)
    os.makedirs(OUT_ZIPS_DIR, exist_ok=True)
    
    zips = glob.glob(os.path.join(ZIPS_DIR, "*.zip"))
    print(f"Found {len(zips)} zip files to process.")
    
    processed_robots = []
    
    for zpath in zips:
        zip_name = os.path.basename(zpath)
        print(f"\n========================================")
        print(f"Extracting and processing {zip_name}...")
        print(f"========================================")
        
        extracted_dir = os.path.join(TEMP_DIR, zip_name.replace('.zip', ''))
        os.makedirs(extracted_dir, exist_ok=True)
        
        with zipfile.ZipFile(zpath, 'r') as z:
            z.extractall(extracted_dir)
            
        if "universal_robot" in zip_name:
            # Special dynamic yaml compiling for UR
            names = convert_ur_robots(extracted_dir)
            processed_robots.extend(names)
        else:
            # Standard macro extraction for other brands
            colors = get_all_colors_in_extracted_dir(extracted_dir)
            print(f"Extracted {len(colors)} color definitions from xacros.")
            
            # Find all macro xacros
            macro_files = []
            for r, d, files in os.walk(extracted_dir):
                for f in files:
                    if f.endswith('_macro.xacro') and 'gazebo' not in r.lower():
                        macro_files.append(os.path.join(r, f))
                        
            print(f"Found {len(macro_files)} macro files.")
            for mfile in macro_files:
                name = convert_standard_macro(mfile, extracted_dir, colors)
                if name:
                    processed_robots.append(name)
                    

    PRE_EXISTING_ROBOTS = {
        "COMAUSMART_NJ_500-2.7", "GANTRY", "IR-R35JQR", "KR10R1100SIXX", "KR10R1420", 
        "KUKA_KR10R1420HP", "KR10R900_2", "KR120R2500PRO", "KR150R3100_2", "KR150_2", 
        "KR16_2", "KR210L150", "KUKA_KR210R2700-2", "KUKA_KR360R2830", "KR3R540", "KUKA_KR480R3330MT", 
        "KUKA_KR500R2380", "KR5_ARC", "KR6R700SIXX", "KR6R900SIXX", "KR6R900_2", 
        "LBR_IIWA_14_R820", "TAPEPLACEMENTGANTRY"
    }
    
    print("\nCleaning up old non-prefixed folders and zip files...")
    for d in os.listdir(ROBOTS_DIR):
        d_path = os.path.join(ROBOTS_DIR, d)
        if os.path.isdir(d_path) and d.upper() not in PRE_EXISTING_ROBOTS:
            is_prefixed = False
            for prefix in ['KUKA_', 'ABB_', 'FANUC_', 'MOTOMAN_', 'STAUBLI_', 'UR_']:
                if d.startswith(prefix):
                    is_prefixed = True
                    break
            if not is_prefixed:
                print(f"Removing old non-prefixed folder: {d}")
                shutil.rmtree(d_path, ignore_errors=True)
                
    # Clean Robots_Zip/ zip files
    for f in os.listdir(OUT_ZIPS_DIR):
        f_path = os.path.join(OUT_ZIPS_DIR, f)
        if f.endswith('.zip'):
            name = f[:-4]
            if name.upper() not in PRE_EXISTING_ROBOTS:
                is_prefixed = False
                for prefix in ['KUKA_', 'ABB_', 'FANUC_', 'MOTOMAN_', 'STAUBLI_', 'UR_']:
                    if name.startswith(prefix):
                        is_prefixed = True
                        break
                if not is_prefixed:
                    print(f"Removing old non-prefixed zip: {f}")
                    try:
                        os.remove(f_path)
                    except:
                        pass

    # Generate Zip Archives and Update Catalog
    print("\n========================================")
    print("Generating Zip Archives for new robots...")
    print("========================================")
    for robot in sorted(set(processed_robots)):
        source_robot_dir = os.path.join(ROBOTS_DIR, robot)
        if os.path.exists(source_robot_dir):
            zip_base = os.path.join(OUT_ZIPS_DIR, robot)
            print(f"Archiving {robot}...")
            # We want the archive to contain the visual, collision folders and the urdf directly
            shutil.make_archive(zip_base, 'zip', ROBOTS_DIR, robot)
            
    print("\n========================================")
    print("Updating catalog.json...")
    print("========================================")
    catalog_path = os.path.join(DATA_DIR, "catalog.json")
    if os.path.exists(catalog_path):
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = json.load(f)
    else:
        catalog = {"version": "1.0", "models": []}
        
    # Build dictionary of existing entries to avoid duplicates and preserve parameters
    # Keep original KUKA, Comau, Gantry, Inovance robots, and all Tools, Tracks, Positioners
    ORIGINAL_ROBOTS = {
        "COMAUSMART_NJ_500-2.7", "GANTRY", "IR-R35JQR", "KR10R1100SIXX", "KR10R1420", 
        "KR10R1420HP", "KR10R900_2", "KR120R2500PRO", "KR150R3100_2", "KR150_2", 
        "KR16_2", "KR210L150", "KR210R2700-2", "KR360R2830", "KR3R540", "KR480R3330MT", 
        "KR500R2380", "KR5_ARC", "KR6R700SIXX", "KR6R900SIXX", "KR6R900_2", 
        "LBR_IIWA_14_R820", "TAPEPLACEMENTGANTRY"
    }
    
    existing_models = {}
    for m in catalog["models"]:
        name = m["name"]
        m_type = m.get("type", "Robot")
        if m_type != "Robot" or name in ORIGINAL_ROBOTS:
            existing_models[name] = m
    
    for robot in sorted(set(processed_robots)):
        origin_name = robot.replace("KUKA_", "").replace("ABB_", "").replace("FANUC_", "").replace("MOTOMAN_", "").replace("STAUBLI_", "").replace("UR_", "")
        
        spec = ROBOT_SPECS.get(origin_name, {"brand": "Unknown", "payload": 0.0, "reach": 0.0})
        
        brand = spec["brand"]
        if brand == "Unknown" or brand == "custom":
            if robot.startswith("ABB_"):
                brand = "ABB"
            elif robot.startswith("MOTOMAN_"):
                brand = "MOTOMAN"
            elif robot.startswith("STAUBLI_"):
                brand = "STAUBLI"
            elif robot.startswith("FANUC_"):
                brand = "FANUC"
            elif robot.startswith("UR_"):
                brand = "UR"
            elif robot.startswith("KUKA_"):
                brand = "KUKA"
            elif "CSDA10F" in robot or "MA2010" in robot or "MOTOPOS" in robot or "MPX1950" in robot or "MS210" in robot or "TORSO" in robot:
                brand = "MOTOMAN"
            elif "R2000IC" in robot:
                brand = "FANUC"
            else:
                brand = "Custom"
                
        urdf_rel_path = f"Robots/{robot}/{robot}.urdf"
        zip_url = f"https://storage.fiber-art.myshawn.com/Robots/{robot}.zip"
        
        model_entry = {
            "type": "Robot",
            "name": robot,
            "brand": brand,
            "payload_kg": spec.get("payload", 0.0),
            "reach_m": spec.get("reach", 0.0),
            "urdf": urdf_rel_path,
            "zip_url": zip_url
        }
        
        # Add or update
        existing_models[robot] = model_entry
        
    catalog["models"] = list(existing_models.values())
    
    with open(catalog_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully updated catalog.json with {len(catalog['models'])} entries.")
    
    # Cleanup temp directory
    clean_temp_dir()
    print("Cleanup completed successfully!")

if __name__ == "__main__":
    main()
