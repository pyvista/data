## PyVista Example Data Repository

This data was originally cloned from git://vtk.org/VTKData.git. These files
are used for examples in both PyVista and PVGeo.

### Consuming these files

If you're using ``pyvista>=0.37.0`` you can download these files with:

```py
from pyvista import examples

filename = examples.download_file('my-directory/my-file.vtk')
```

This assumes the file has been uploaded to the `Data` directory as
`Data/my-directory/my-file.vtk`.

### Dataset metadata

[`DATASETS.toml`](DATASETS.toml) describes every file under `Data/`: what it
is, where it came from, who made it, what licence it carries and what changed
between the source and the copy here. PyVista reads it and publishes it in the
[Dataset Gallery](https://docs.pyvista.org/api/examples/dataset-gallery)
alongside each dataset.

Read a single dataset's record with:

```py
import tomllib
import urllib.request

url = 'https://raw.githubusercontent.com/pyvista/data/master/DATASETS.toml'
with urllib.request.urlopen(url) as response:
    metadata = tomllib.loads(response.read().decode())

by_name = {entry['name']: entry for entry in metadata['dataset']}
shark = by_name['grey_nurse_shark']
print(shark['SPDX-License-Identifier'], shark['source_url'])
```

The licensing keys follow the [REUSE specification](https://reuse.software),
so `SPDX-License-Identifier` and `SPDX-FileCopyrightText` mean exactly what
they mean there. Full licence texts live in [`LICENSES/`](LICENSES).

### Adding new datasets

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: add the files under `Data/`,
add a `[[dataset]]` block to `DATASETS.toml`, and run

```bash
python tools/validate_datasets.py
```

`LICENSE`, `README`, `CITATION` and `.license` files are **not** accepted under
`Data/`; that information belongs in `DATASETS.toml` where PyVista can read it.
CI enforces both rules on every pull request.

### Adding the Example to PyVista's Downloads

See the documentation within
[downloads.py](https://github.com/pyvista/pyvista/blob/main/pyvista/examples/downloads.py)
for adding a new method to download the example file within the
``pyvista.examples`` module.

### Reporting a license concern

If you believe a dataset in this repository is distributed under incorrect or
insufficient license terms, or you can identify the origin of one of the
`LicenseRef-Unknown` entries, please open an issue. We take license compliance
seriously.
