#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["coacd", "trimesh", "lxml", "pycollada"]
# ///

import os
import sys
import argparse
import glob
import shutil
import trimesh
import coacd
from lxml import etree

def generate_convex_decomposition(
    input_path, output_path, threshold=0.2, merge=False, max_convex_hulls=5
):
    """
    Generate up to max_convex_hulls convex parts using CoACD and save them
    as one mesh file at output_path.
    """
    try:
        mesh_parts = decompose_mesh(input_path, threshold, merge, max_convex_hulls)
        # Store all convex parts in one STL; each part remains a separate hull.
        result_mesh = trimesh.util.concatenate(mesh_parts)
        
        # Save to output path
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        result_mesh.export(output_path)
        return True
    except Exception as e:
        print(f"Exception during convex hull generation for {input_path}: {e}")
        return False


def decompose_mesh(input_path, threshold=0.2, merge=False, max_convex_hulls=5):
    mesh = trimesh.load(input_path, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"Input {input_path} is not a valid 3D mesh.")

    coacd_mesh = coacd.Mesh(mesh.vertices, mesh.faces)
    parts = coacd.run_coacd(
        coacd_mesh,
        max_convex_hull=max_convex_hulls,
        threshold=threshold,
        preprocess_mode='off',
        merge=merge,
    )
    if not parts:
        raise ValueError(f"CoACD failed to generate any part for {input_path}.")

    if len(parts) > max_convex_hulls:
        # Some CoACD builds ignore max_convex_hull when merge is disabled.
        parts = sorted(
            parts,
            key=lambda part: abs(
                trimesh.Trimesh(vertices=part[0], faces=part[1]).volume
            ),
            reverse=True,
        )[:max_convex_hulls]
        print(f"  Retaining {len(parts)} largest convex hulls.")

    return [trimesh.Trimesh(vertices=vs, faces=fs) for vs, fs in parts]


def generate_convex_decomposition_parts(
    input_path, output_dir, output_stem, threshold=0.2, merge=False, max_convex_hulls=5
):
    try:
        mesh_parts = decompose_mesh(input_path, threshold, merge, max_convex_hulls)
        os.makedirs(output_dir, exist_ok=True)
        output_paths = []
        for index, mesh_part in enumerate(mesh_parts, start=1):
            output_path = os.path.join(output_dir, f"{output_stem}_{index}.stl")
            mesh_part.export(output_path)
            output_paths.append(output_path)
        return output_paths
    except Exception as e:
        print(f"Exception during convex hull generation for {input_path}: {e}")
        return []

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

def process_urdf(
    urdf_path,
    regenerate=False,
    threshold=0.2,
    merge=False,
    max_convex_hulls=5,
):
    """
    Generate collision meshes for one URDF/positioner and update its XML.
    """
    try:
        parser = etree.XMLParser(remove_blank_text=True)
        tree = etree.parse(urdf_path, parser)
        root = tree.getroot()
        urdf_dir = os.path.dirname(urdf_path)
        urdf_modified = False

        if regenerate:
            for link in root.xpath("//link"):
                for collision_el in link.xpath("collision"):
                    link.remove(collision_el)
            collision_dir = os.path.join(urdf_dir, "collision")
            if os.path.isdir(collision_dir):
                shutil.rmtree(collision_dir)
            urdf_modified = True

        for link in root.xpath("//link"):
            link_name = link.get("name")
            visual_meshes = link.xpath("visual/geometry/mesh")
            if not visual_meshes:
                continue

            visual_mesh_rel = visual_meshes[0].get("filename")
            if not visual_mesh_rel:
                continue

            collision_meshes = link.xpath("collision/geometry/mesh")
            if collision_meshes and not regenerate:
                collision_files_exist = bool(collision_meshes) and all(
                    mesh.get("filename")
                    and os.path.isfile(os.path.join(urdf_dir, mesh.get("filename")))
                    for mesh in collision_meshes
                )
                if collision_files_exist:
                    continue

            print(f"\nProcessing link '{link_name}' in {os.path.basename(urdf_path)}.")
            visual_mesh_abs = os.path.join(urdf_dir, visual_mesh_rel)
            if not os.path.exists(visual_mesh_abs):
                print(f"  Warning: Visual mesh not found at {visual_mesh_abs}. Skipping.")
                continue

            print(f"  Generating up to {max_convex_hulls} convex hulls from {visual_mesh_rel}...")
            collision_paths = generate_convex_decomposition_parts(
                visual_mesh_abs,
                os.path.join(urdf_dir, "collision"),
                link_name,
                threshold,
                merge,
                max_convex_hulls,
            )

            if not collision_paths:
                print(f"  Failed to generate collision mesh for link {link_name}.")
                continue

            print(f"  Successfully generated {len(collision_paths)} collision mesh(es).")
            for collision_el in link.xpath("collision"):
                link.remove(collision_el)

            visual_els = link.xpath("visual")
            insert_index = link.index(visual_els[-1]) + 1 if visual_els else len(link)
            for collision_path in collision_paths:
                collision_rel = os.path.relpath(collision_path, urdf_dir).replace(os.sep, "/")
                collision_el = etree.Element("collision", name="collision")
                geom_el = etree.SubElement(collision_el, "geometry")
                etree.SubElement(geom_el, "mesh", filename=collision_rel)
                link.insert(insert_index, collision_el)
                insert_index += 1
            urdf_modified = True

        if urdf_modified:
            formatted_xml = format_urdf_string(root)
            with open(urdf_path, "w", encoding="utf-8") as f:
                f.write(formatted_xml)
            print(f"Updated URDF: {urdf_path}")
    except Exception as e:
        print(f"Error processing URDF {urdf_path}: {e}")

def main():
    parser = argparse.ArgumentParser(description="MeshTools: Convert input mesh to convex hull(s) using CoACD, or scan for missing collisions in Robots/.")
    parser.add_argument("-i", "--input", dest="input", help="Input mesh file (STL/DAE/OBJ/etc.)")
    parser.add_argument("-o", "--output", dest="output", help="Output mesh file (STL)")
    parser.add_argument("--scan", action="store_true", help="Scan Robots/ folder, generate missing collisions, and update URDFs.")
    parser.add_argument("--urdf", help="Regenerate collisions for one URDF or .positioner file.")
    parser.add_argument("--regenerate", action="store_true", help="Delete existing collision XML nodes and the collision folder before generating.")
    parser.add_argument("--threshold", type=float, default=0.2, help="CoACD concavity threshold (default: 0.2).")
    parser.add_argument("--merge", action=argparse.BooleanOptionalAction, default=False, help="Allow CoACD to merge convex parts (default: false).")
    parser.add_argument("--max-convex-hulls", type=int, default=5, help="Maximum convex hulls per visual mesh (default: 5).")
    
    args = parser.parse_args()

    if args.max_convex_hulls < 1:
        parser.error("--max-convex-hulls must be at least 1.")
    if args.threshold < 0:
        parser.error("--threshold must be non-negative.")
    
    # Locate ROBOTS_DIR dynamically
    script_dir = os.path.dirname(os.path.abspath(__file__))
    robots_dir = os.path.join(os.path.dirname(script_dir), "Robots")
    
    if args.urdf:
        process_urdf(
            args.urdf,
            regenerate=args.regenerate,
            threshold=args.threshold,
            merge=args.merge,
            max_convex_hulls=args.max_convex_hulls,
        )
    elif args.scan or (not args.input and not args.output):
        # Scan mode
        urdfs = glob.glob(os.path.join(robots_dir, "**", "*.urdf"), recursive=True)
        print(f"Scanning for URDF files under {robots_dir}... Found {len(urdfs)} URDF files.")
        for urdf_path in sorted(urdfs):
            process_urdf(
                urdf_path,
                regenerate=args.regenerate,
                threshold=args.threshold,
                merge=args.merge,
                max_convex_hulls=args.max_convex_hulls,
            )
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
        parts = coacd.run_coacd(
            coacd_mesh,
            threshold=args.threshold,
            merge=args.merge,
            max_convex_hull=args.max_convex_hulls,
        )
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
