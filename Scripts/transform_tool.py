#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["trimesh", "lxml", "numpy"]
# ///

"""
transform_tool.py ? Apply local_pose to link meshes and remove local_pose from tool description.

Reads a .tool or .jointed_tool file, applies the <local_pose>
transformation (xyz + rpy) to every referenced STL mesh, backs up originals,
then removes <local_pose> from the XML.

Usage:
    uv run Scripts/transform_tool.py path/to/Tool.tool
    uv run Scripts/transform_tool.py path/to/Tool.jointed_tool
"""

import re
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path

import numpy as np
import trimesh
from lxml import etree


def parse_rpy_value(value: str) -> float:
    """Parse an rpy component, handling ${radians(deg)} syntax."""
    value = value.strip()
    m = re.match(r'\$\{radians\(([^)]+)\)\}', value)
    if m:
        return float(m.group(1)) * np.pi / 180.0
    return float(value)


def rpy_to_rotation_matrix(roll: float, pitch: float, yaw: float) -> np.ndarray:
    """Build rotation matrix from roll-pitch-yaw (radians) ? Rz(yaw) * Ry(pitch) * Rx(roll)."""
    cx, sx = np.cos(roll), np.sin(roll)
    cy, sy = np.cos(pitch), np.sin(pitch)
    cz, sz = np.cos(yaw), np.sin(yaw)

    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def build_transform(xyz: str, rpy: str) -> np.ndarray:
    """Build 4x4 homogeneous transform from xyz and rpy attribute strings."""
    tx, ty, tz = [float(v.strip()) for v in xyz.split()]
    r, p, y = [parse_rpy_value(v) for v in rpy.split()]
    R = rpy_to_rotation_matrix(r, p, y)
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = [tx, ty, tz]
    return T


def process_tool(tool_path: str) -> None:
    tool_path = Path(tool_path).resolve()
    if not tool_path.exists():
        print(f"Error: {tool_path} does not exist.")
        sys.exit(1)

    tool_dir = tool_path.parent
    print(f"Reading {tool_path.name} ...")

    # ?? Parse XML ??????????????????????????????????????????????????????
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(tool_path), parser)
    root = tree.getroot()

    local_pose = root.find("local_pose")
    if local_pose is None:
        print("No <local_pose> found ? nothing to do.")
        return

    xyz = local_pose.get("xyz", "0 0 0")
    rpy = local_pose.get("rpy", "0 0 0")
    print(f"  local_pose: xyz=\"{xyz}\"  rpy=\"{rpy}\"")

    # ?? Back up ????????????????????????????????????????????????????????
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = tool_dir / "backup" / stamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Copy the original tool description
    shutil.copy2(str(tool_path), str(backup_dir / tool_path.name))
    print(f"  Backed up {tool_path.name} to {backup_dir / tool_path.name}")

    # ?? Collect mesh files ?????????????????????????????????????????????
    transform = build_transform(xyz, rpy)
    mesh_files = set()

    for link in root.findall(".//link"):
        for geom in link.findall(".//geometry/mesh"):
            filename = geom.get("filename")
            if filename:
                abs_path = (tool_dir / filename).resolve()
                mesh_files.add(abs_path)

    if not mesh_files:
        print("No <mesh> files found in links.")
        return

    print(f"  Found {len(mesh_files)} mesh file(s) to transform.")

    # ?? Transform each mesh ????????????????????????????????????????????
    for mesh_path in sorted(mesh_files):
        if not mesh_path.exists():
            print(f"  Warning: {mesh_path} not found, skipping.")
            continue

        # Backup
        rel = mesh_path.relative_to(tool_dir)
        bak = backup_dir / rel
        bak.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(mesh_path), str(bak))
        print(f"  Backed up {rel} ? backup/{stamp}/{rel}")

        # Load & transform
        mesh = trimesh.load(str(mesh_path), force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            print(f"  Warning: {rel} is not a valid mesh, skipping.")
            continue

        verts = mesh.vertices
        # Apply homogeneous transform: [x' y' z' 1] = M * [x y z 1]
        verts_h = np.column_stack([verts, np.ones(len(verts))])
        verts_transformed = (transform @ verts_h.T).T[:, :3]

        mesh = mesh.copy()
        mesh.vertices = verts_transformed
        mesh.export(str(mesh_path))
        print(f"  Transformed {rel} ? overwritten in place")

    # ?? Remove local_pose ??????????????????????????????????????????????
    root.remove(local_pose)
    print("  Removed <local_pose> from tool description.")

    # ?? Write updated XML ??????????????????????????????????????????????
    xml_bytes = etree.tostring(root, encoding="utf-8", xml_declaration=True, pretty_print=True)
    xml_str = xml_bytes.decode("utf-8")
    xml_str = xml_str.replace("<?xml version='1.0' encoding='utf-8'?>",
                              '<?xml version="1.0" encoding="utf-8"?>')

    with open(str(tool_path), "w", encoding="utf-8") as f:
        f.write(xml_str)
    print(f"  Updated {tool_path.name} written.")

    print("\nDone. Original files backed up to backup/%s/" % stamp)


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    for arg in sys.argv[1:]:
        if not (arg.endswith(".tool") or arg.endswith(".jointed_tool")):
            print(f"Warning: {arg} does not end with .tool or .jointed_tool, skipping.")
            continue
        process_tool(arg)


if __name__ == "__main__":
    main()
