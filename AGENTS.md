# Python Script
- **Never** install packages to the global Python environment via `pip install`.
- Use **uv script mode** ([PEP 723](https://peps.python.org/pep-0723/)) with
  inline dependency declarations.
- Place one-off scripts in `temp/`.
- Place reusable scripts in `Scripts/`

```python
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
# ... script body ...
```

Run with:
```bash
uv run temp/my_script.py
```

> **Note**: `uv` automatically creates an isolated environment, downloads de-
> pendencies, and caches them. No global installation, no venv management.

---

# Scripts Overview

## `Scripts/generate_catalog.py`
Generates `catalog.json` from URDF files in the `Robots/`, `Tracks/`,
`Positioners/`, `Tools/` directories.

**What it does:**
1. Scans each category directory for URDF/definition files
2. Reads `brand`, `payload`, `reach` attributes from the root XML element
3. Creates zip archives in `{Category}_Zip/`
4. Writes `catalog.json` with all models and their metadata

```bash
uv run --with lxml Scripts/generate_catalog.py
```

## `Scripts/upload_to_r2.py`
Uploads zip archives and `catalog.json` to Cloudflare R2 storage.

**What it does:**
1. Reads `catalog.json` to discover all models
2. Zips each model folder into `{Category}_Zips/`
3. Uploads only changed files (MD5-based dedup) to R2
4. Uploads `catalog.json` last

**Requirements:** `.env` file with R2 credentials:
```
CloudFlareAPI_FiberArt_S3_API=<endpoint>
CloudFlareAPI_FiberArt_S3_ID=<access_key>
CloudFlareAPI_FiberArt_S3_SECRET=<secret_key>
R2_BUCKET_NAME=fiber-art
```

```bash
uv run --with boto3 --with python-dotenv --with tqdm Scripts/upload_to_r2.py
```

## `Scripts/generate_collision_mesh.py`
Generates collision meshes from visual meshes using CoACD (convex
decomposition).

```bash
# Scan all Robots/ and auto-generate missing collision meshes
uv run Scripts/generate_collision_mesh.py --scan

# Single file: decompose a mesh into convex hulls
uv run Scripts/generate_collision_mesh.py -i input.stl -o output.stl
```

## `Scripts/convert_ros_zips.py`
Converts ROS xacro-based robot packages from `ros-robots/` into standalone URDF
files under `Robots/`. Handles UR (Universal Robots), KUKA, ABB, FANUC,
MOTOMAN, and STAUBLI formats.

---

# Adding a New Robot Model

## Workflow

### Step 1: Prepare the URDF
Create a new folder under `Robots/<RobotName>/` containing:
- `<RobotName>.urdf` — the URDF definition
- `visual/` — visual mesh files (STL/DAE)
- `collision/` — collision mesh files (STL), optional

The root `<robot>` element MUST include these attributes:
```xml
<robot name="Brand_ModelName" payload="12" reach="1.5" brand="Brand" type="Robot">
```

- `name` — use `Brand_ModelName` convention (e.g. `FANUC_LRMATE200ID7L`)
- `brand` — brand name (ABB, FANUC, KUKA, MOTOMAN, STAUBLI, UR, Custom, etc.)
- `type` — usually `Robot`. Also valid: `Track`, `Positioner`, `Tool`
- `payload` — max payload in **kg**
- `reach` — max reach in **meters**

Model specs can be found at:
- [RoboDK Robot Library](https://robodk.com/library) — search by model name
- Manufacturer datasheets / official websites

### Step 2: Generate collision meshes (if needed)
```bash
uv run Scripts/generate_collision_mesh.py --scan
```

### Step 3: Regenerate catalog and zip files
```bash
uv run --with lxml Scripts/generate_catalog.py
```

### Step 4: Verify
```bash
uv run --with stdlib-list python -c "
import json
d = json.load(open('catalog.json'))
missing_p = [m['name'] for m in d['models'] if m['type']=='Robot' and 'payload' not in m]
missing_r = [m['name'] for m in d['models'] if m['type']=='Robot' and 'reach' not in m]
print(f'Robots missing payload: {len(missing_p)}')
print(f'Robots missing reach:   {len(missing_r)}')
"
```

### Step 5: Upload to R2
```bash
uv run --with boto3 --with python-dotenv --with tqdm Scripts/upload_to_r2.py
```

## Directory Structure
```
FiberArtData/
├── Robots/                  # Robot URDF files (one folder per model)
│   └── Brand_ModelName/
│       ├── Brand_ModelName.urdf
│       ├── visual/          # Visual meshes
│       └── collision/       # Collision meshes
├── Tracks/                  # Track definitions (.track)
├── Positioners/             # Positioner definitions (.positioner)
├── Tools/                   # Tool definitions (.jointless_tool, .jointed_tool)
├── Scripts/                 # Reusable automation scripts
├── temp/                    # One-off scripts
├── ros-robots/              # Source ROS xacro packages (input for convert_ros_zips.py)
├── Robots_Zip/              # Generated zip archives (by generate_catalog.py)
├── Robots_Zips/             # Generated zip archives (by upload_to_r2.py)
└── catalog.json             # Model catalog (generated, do not edit manually)
```