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

### Adding the Example to PyVista's Downloads

See the documentation within
[downloads.py](https://github.com/pyvista/pyvista/blob/main/pyvista/examples/downloads.py)
for adding a new method to download the example file within the
``pyvista.examples`` module.

### Adding new datasets (licensing requirements)

Every dataset in this repository must have a clear, permissive license
compatible with redistribution from a BSD-licensed project (pyvista).
Contributors adding new data MUST:

1. **Confirm the original source.** Record where the dataset came from
   (URL, paper, repository, upload page). If you can't identify the
   origin, do not submit it.

2. **Identify the license explicitly.** Read the license at the source
   — do not guess from context. Record the SPDX identifier where one
   exists (e.g. `CC0-1.0`, `CC-BY-4.0`, `MIT`).

3. **Verify the license allows commercial use.** Datasets under
   non-commercial licenses (e.g. CC BY-NC, CC BY-NC-SA, CC BY-NC-ND,
   "academic / research use only", "personal use only") are not
   accepted unless explicitly approved by the maintainers and
   prominently flagged.

4. **Provide a license file alongside the dataset.** For a dataset that
   has its own directory, add a `LICENSE` file inside it. For a dataset
   that sits as a loose file in `Data/`, add a `<filename>.license`
   companion file. The license file must contain:

   - The source URL.
   - The verbatim license statement or a link to it.
   - The required attribution text, if any.
   - An `SPDX-License-Identifier:` line.

5. **Prefer CC0 and public-domain sources** when possible — they impose
   no attribution or ShareAlike burden on downstream users. Good
   sources include Smithsonian Open Access (https://3d.si.edu/cc0) and
   US government works.

6. **Be cautious with ShareAlike licenses** (CC BY-SA, ODbL). These
   are accepted but must be clearly labeled, because downstream
   users who derive new work from the dataset inherit the ShareAlike
   obligation.

When opening a pull request, fill in the checklist in the PR template.
PRs without license documentation will not be merged.

### Reporting a license concern

If you believe a dataset in this repository is distributed under
incorrect or insufficient license terms, please open an issue. We take
license compliance seriously.
