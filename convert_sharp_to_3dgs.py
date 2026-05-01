"""
Convert SHARP .ply files to standard 3DGS .ply format.

SHARP format has:  x y z f_dc(3) opacity scale(3) rot(4)  + non-standard camera elements
Standard 3DGS has: x y z nx ny nz f_dc(3) f_rest(45) opacity scale(3) rot(4)

Missing fields (normals, f_rest) are filled with zeros.
"""

import os
import struct
import numpy as np
from pathlib import Path

INPUT_DIR  = Path(__file__).parent / "SHARP"
OUTPUT_DIR = Path(__file__).parent / "SHARP_converted"

# Target header for standard 3DGS
def build_target_header(n_vertices: int) -> bytes:
    lines = ["ply", "format binary_little_endian 1.0", f"element vertex {n_vertices}"]
    lines += ["property float x", "property float y", "property float z"]
    lines += ["property float nx", "property float ny", "property float nz"]
    lines += ["property float f_dc_0", "property float f_dc_1", "property float f_dc_2"]
    lines += [f"property float f_rest_{i}" for i in range(45)]
    lines += ["property float opacity"]
    lines += ["property float scale_0", "property float scale_1", "property float scale_2"]
    lines += ["property float rot_0", "property float rot_1", "property float rot_2", "property float rot_3"]
    lines += ["end_header"]
    return ("\n".join(lines) + "\n").encode("ascii")


def parse_header(f):
    """Read PLY header, return (n_vertices, byte_offset_to_vertex_data, property_list)."""
    header_lines = []
    while True:
        line = f.readline().decode("ascii").strip()
        header_lines.append(line)
        if line == "end_header":
            break

    n_vertices = 0
    properties = []
    in_vertex = False
    for line in header_lines:
        if line.startswith("element vertex"):
            n_vertices = int(line.split()[-1])
            in_vertex = True
        elif line.startswith("element") and not line.startswith("element vertex"):
            in_vertex = False
        elif line.startswith("property") and in_vertex:
            parts = line.split()
            properties.append((parts[1], parts[2]))  # (type, name)

    return n_vertices, properties


DTYPE_MAP = {"float": np.float32, "uint": np.uint32, "int": np.int32, "uchar": np.uint8}


def convert(input_path: Path, output_path: Path):
    with open(input_path, "rb") as f:
        n_vertices, properties = parse_header(f)
        vertex_data_offset = f.tell()

        # Read only the vertex block (skip non-standard trailing elements)
        bytes_per_vertex = sum(np.dtype(DTYPE_MAP[t]).itemsize for t, _ in properties)
        raw = f.read(n_vertices * bytes_per_vertex)

    # Parse into structured array
    dt = np.dtype([(name, DTYPE_MAP[t]) for t, name in properties])
    verts = np.frombuffer(raw, dtype=dt)

    n = n_vertices
    zeros = np.zeros(n, dtype=np.float32)

    # Build output array: 62 floats per vertex
    # [x y z | nx ny nz | f_dc(3) | f_rest(45) | opacity | scale(3) | rot(4)]
    out = np.zeros((n, 62), dtype=np.float32)
    out[:, 0]  = verts["x"]
    out[:, 1]  = verts["y"]
    out[:, 2]  = verts["z"]
    # cols 3,4,5 = nx,ny,nz — stay zero
    out[:, 6]  = verts["f_dc_0"]
    out[:, 7]  = verts["f_dc_1"]
    out[:, 8]  = verts["f_dc_2"]
    # cols 9..53 = f_rest_0..44 — stay zero
    out[:, 54] = verts["opacity"]
    out[:, 55] = verts["scale_0"]
    out[:, 56] = verts["scale_1"]
    out[:, 57] = verts["scale_2"]
    out[:, 58] = verts["rot_0"]
    out[:, 59] = verts["rot_1"]
    out[:, 60] = verts["rot_2"]
    out[:, 61] = verts["rot_3"]

    header = build_target_header(n_vertices)
    with open(output_path, "wb") as f:
        f.write(header)
        f.write(out.tobytes())

    print(f"  {input_path.name}  →  {output_path.name}  ({n_vertices:,} vertices)")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    ply_files = sorted(INPUT_DIR.glob("*.ply"))
    if not ply_files:
        print(f"No .ply files found in {INPUT_DIR}")
        return

    print(f"Converting {len(ply_files)} file(s) → {OUTPUT_DIR}\n")
    for src in ply_files:
        dst = OUTPUT_DIR / src.name
        convert(src, dst)
    print("\nDone.")


if __name__ == "__main__":
    main()
