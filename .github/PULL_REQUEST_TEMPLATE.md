<!-- Thank you for contributing a dataset to pyvista/data! -->

## Summary

<!-- What are you adding or changing, and why? -->

## Dataset checklist

Only needed if this PR adds or changes files under `Data/`. See
[CONTRIBUTING.md](https://github.com/pyvista/data/blob/master/CONTRIBUTING.md)
for the field reference.

- [ ] I added a `[[dataset]]` block to `DATASETS.toml` for every file I added,
      in alphabetical order by `name`.
- [ ] I did **not** add a `LICENSE`, `README`, `CITATION` or `.license` file
      under `Data/`.
- [ ] I read the licence **at the source** and recorded it in
      `SPDX-License-Identifier`. I did not guess.
- [ ] The licence permits redistribution from this repository (Apache-2.0)
      and from PyVista (MIT), and permits commercial use. (Non-commercial data needs maintainer approval
      and `commercial_use = false` on its `[license.*]` table.)
- [ ] If the licence requires credit, I filled in `attribution`.
- [ ] If I changed the data after downloading it, I set `modified = true` and
      described the change in `modification`.
- [ ] `python tools/validate_datasets.py` passes locally.
