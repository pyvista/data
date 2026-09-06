# Procedural cow

`cow.pv` is a colored cow with 300,000 triangles, rounded cloven hooves with flat
soles, and an opaque, tapered approximation of the tail hair. It is one connected,
watertight `pyvista.PolyData` surface, 200 mm long, with Z up.

Geometry and appearance are contained in this **single pyvista-zstd file**. The
black-and-white coat and other colors are embedded as the active `RGB` uint8 point
array. There is no external texture image.

```python
import pyvista as pv

cow = pv.read("cow.pv")
cow.plot(scalars="RGB", rgb=True, smooth_shading=True)
```

Reading the file requires `pyvista-zstd`, available through `pyvista[io]`.

## Reproduce

From this directory, with `uv` installed:

```sh
uv run --locked generate_cow.py
```

The script writes only `cow.pv` by default. The dependency lock and Python version
file define the tested environment. Generation uses NumPy, SciPy, PyVista, and
pyvista-zstd; it does not require Trimesh. No downloaded geometry or textures are
used during generation.

Optional review renders show the isolated hoof from three directions, its soles,
its connection to the lower leg, all four feet cropped from the final cow, and the
full colored model reloaded from disk:

```sh
uv run --locked generate_cow.py --preview-dir /tmp/cow-preview
```

The same hoof construction is used for the isolated views and all four feet.
Edit `HoofConfig` in the script to adjust the hoof dimensions. `--triangles`,
`--length-mm`, and `--voxel-size` control mesh budget, export scale, and the source
field resolution. The default field uses 55.25 million float32 samples (221 MB);
temporary arrays and rendering require additional memory. Each primitive updates
only its local bounding box.

Every run checks the triangle count, closed manifold topology, face winding, one
connected component, nondegenerate faces, positive volume, and four broad coplanar
soles. It then reloads the `.pv` and requires exact equality of point coordinates,
triangle connectivity, and embedded RGB values. The active color array is also
checked. Independent rebuilds produced identical points, triangle connectivity,
and RGB values. The compressed files can differ because the format records
process-specific array identifiers.

## Source and license

This is an original procedural model generated with assistance from OpenAI Codex
on 2026-09-06. Its source is the accompanying `generate_cow.py`, prepared for the
[PyVista data repository](https://github.com/pyvista/data). The hoof outline was
visually compared with a [photograph of a cow hoof](https://www.schaette.de/ratgeber/klauengesundheit-auch-ein-stoffwechselthema);
no photograph data is included in the geometry or color array.

The model and generation code are provided under CC0-1.0. See `LICENSE`.
