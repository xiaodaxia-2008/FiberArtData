#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["coacd", "trimesh"]
# ///

import argparse
import trimesh
import coacd
import sys

def main():
    parser = argparse.ArgumentParser(description="MeshTools: Convert input mesh to convex hull(s) using CoACD.")
    parser.add_argument("-i", "--input", required=True, dest="input", help="Input STL file")
    parser.add_argument("-o", "--output", required=True, dest="output", help="Output STL file")
    
    args = parser.parse_args()

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
