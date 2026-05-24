#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["coacd", "trimesh", "lxml", "pycollada"]
# ///

import os
import sys
import argparse
import glob
import trimesh
import coacd
from lxml import etree

def generate_single_convex_hull(input_path, output_path):
    """
    Generate a single convex hull from input mesh file using CoACD
    and save it to output_path.
    """
    try:
        mesh = trimesh.load(input_path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            print(f"Error: Input {input_path} is not a valid 3D mesh.")
            return False
        
        coacd_mesh = coacd.Mesh(mesh.vertices, mesh.faces)
        # Use max_convex_hull=1 to generate a single convex hull (no decomposition)
        parts = coacd.run_coacd(coacd_mesh, max_convex_hull=1, threshold=0.9, preprocess_mode='off')
        
        if not parts:
            print(f"Error: CoACD failed to generate any part for {input_path}.")
            return False
        
        # Convert part back to trimesh
        vs, fs = parts[0]
        result_mesh = trimesh.Trimesh(vertices=vs, faces=fs)
        
        # Save to output path
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        result_mesh.export(output_path)
        return True
    except Exception as e:
        print(f"Exception during convex hull generation for {input_path}: {e}")
        return False

def format_urdf_string(xml_root):
    """
    Pretty format URDF XML.
    """
    # Serialize back with pretty_print=True
    xml_bytes = etree.tostring(xml_root, encoding='utf-8', xml_declaration=True, pretty_print=True)
    xml_str = xml_bytes.decode('utf-8')
    
    # Normalize XML declaration
    xml_str = xml_str.replace("<?xml version='1.0' encoding='utf-8'?>", '<?xml version="1.0" encoding="utf-8"?>')
    xml_str = xml_str.replace("<?xml version='1.0' encoding='UTF-8'?>", '<?xml version="1.0" encoding="utf-8"?>')
    xml_str = xml_str.replace("<?xml version='1.0'?>", '<?xml version="1.0" encoding="utf-8"?>')
    xml_str = xml_str.replace('\r\n', '\n')
    return xml_str

def scan_and_generate_collisions(robots_dir):
    """
    Scan all URDF files under robots_dir, detect links missing a collision model,
    generate single convex hull meshes using CoACD, and update the URDFs.
    """
    print(f"Scanning for URDF files under {robots_dir}...")
    urdfs = glob.glob(os.path.join(robots_dir, "**", "*.urdf"), recursive=True)
    print(f"Found {len(urdfs)} URDF files.")
    
    total_processed = 0
    total_updated_links = 0
    
    for urdf_path in sorted(urdfs):
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(urdf_path, parser)
            root = tree.getroot()
            
            urdf_dir = os.path.dirname(urdf_path)
            urdf_modified = False
            
            # Find all links
            for link in root.xpath("//link"):
                link_name = link.get("name")
                
                # Check for visual mesh
                visual_meshes = link.xpath("visual/geometry/mesh")
                if not visual_meshes:
                    continue
                    
                visual_mesh_rel = visual_meshes[0].get("filename")
                if not visual_mesh_rel:
                    continue
                    
                # Check for existing collision mesh
                collision_meshes = link.xpath("collision/geometry/mesh")
                if collision_meshes:
                    # Already has a collision mesh
                    continue
                    
                # Missing collision mesh! Let's generate it
                print(f"\nLink '{link_name}' in {os.path.basename(urdf_path)} is missing collision.")
                
                # Resolve paths
                visual_mesh_abs = os.path.join(urdf_dir, visual_mesh_rel)
                if not os.path.exists(visual_mesh_abs):
                    print(f"  Warning: Visual mesh not found at {visual_mesh_abs}. Skipping.")
                    continue
                    
                # Collision mesh output filename: collision/<link_name>.stl
                collision_mesh_rel = f"collision/{link_name}.stl"
                collision_mesh_abs = os.path.join(urdf_dir, collision_mesh_rel)
                
                print(f"  Generating single convex hull from {visual_mesh_rel} to {collision_mesh_rel}...")
                success = generate_single_convex_hull(visual_mesh_abs, collision_mesh_abs)
                
                if success:
                    print(f"  Successfully generated collision mesh.")
                    
                    # Create collision XML element
                    collision_el = etree.Element("collision")
                    collision_el.set("name", "collision")
                    geom_el = etree.SubElement(collision_el, "geometry")
                    mesh_el = etree.SubElement(geom_el, "mesh")
                    mesh_el.set("filename", collision_mesh_rel)
                    
                    # Insert after visual if exists, otherwise append
                    visual_els = link.xpath("visual")
                    if visual_els:
                        visual_el = visual_els[-1]
                        idx = link.index(visual_el)
                        link.insert(idx + 1, collision_el)
                    else:
                        link.append(collision_el)
                        
                    urdf_modified = True
                    total_updated_links += 1
                else:
                    print(f"  Failed to generate collision mesh for link {link_name}.")
            
            if urdf_modified:
                # Pretty print and save the modified URDF
                formatted_xml = format_urdf_string(root)
                with open(urdf_path, "w", encoding="utf-8") as f:
                    f.write(formatted_xml)
                print(f"Updated and formatted URDF: {urdf_path}")
                total_processed += 1
                
        except Exception as e:
            print(f"Error processing URDF {urdf_path}: {e}")
            
    print(f"\nScanning completed. Updated {total_updated_links} links in {total_processed} URDF files.")

def main():
    parser = argparse.ArgumentParser(description="MeshTools: Convert input mesh to convex hull(s) using CoACD, or scan for missing collisions in Robots/.")
    parser.add_argument("-i", "--input", dest="input", help="Input mesh file (STL/DAE/OBJ/etc.)")
    parser.add_argument("-o", "--output", dest="output", help="Output mesh file (STL)")
    parser.add_argument("--scan", action="store_true", help="Scan Robots/ folder, generate missing collisions, and update URDFs.")
    
    args = parser.parse_args()
    
    # Locate ROBOTS_DIR dynamically
    script_dir = os.path.dirname(os.path.abspath(__file__))
    robots_dir = os.path.join(os.path.dirname(script_dir), "Robots")
    
    if args.scan or (not args.input and not args.output):
        # Scan mode
        scan_and_generate_collisions(robots_dir)
    else:
        # Single file mode
        if not args.input or not args.output:
            parser.error("Both --input and --output are required for single file mode.")
            
        print(f"Loading mesh from {args.input}...")
        try:
            mesh = trimesh.load(args.input, force="mesh")
        except Exception as e:
            print(f"Error loading mesh: {e}")
            sys.exit(1)
            
        if not isinstance(mesh, trimesh.Trimesh):
            print("Error: Input must be a 3D mesh.")
            sys.exit(1)
            
        print(f"Loaded mesh with {len(mesh.vertices)} vertices and {len(mesh.faces)} faces.")
        
        # Prepare for CoACD
        coacd_mesh = coacd.Mesh(mesh.vertices, mesh.faces)
        
        print("Running Approximate Convex Decomposition via CoACD...")
        parts = coacd.run_coacd(coacd_mesh)
        print(f"Decomposed into {len(parts)} convex parts.")
        
        # Convert parts back to trimesh objects and combine them
        mesh_parts = []
        for vs, fs in parts:
            mesh_parts.append(trimesh.Trimesh(vertices=vs, faces=fs))
            
        result_mesh = trimesh.util.concatenate(mesh_parts)
        
        print(f"Saving combined convex hulls to {args.output}...")
        result_mesh.export(args.output)
        print("Done.")

if __name__ == "__main__":
    main()
