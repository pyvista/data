# Contributing a dataset

Every file under `Data/` is described by exactly one `[[dataset]]` block in
[`DATASETS.toml`](DATASETS.toml). That file is the single source of truth for
what each dataset is, where it came from and how it may be used. PyVista reads
it through `examples.get_example(...).metadata` and publishes it in the
[Dataset Gallery](https://docs.pyvista.org/api/examples/dataset_gallery), so
anything you record here is shown to everyone who downloads the data.

`tools/validate_datasets.py` checks the file on every pull request. Run it
yourself before pushing:

```bash
python tools/validate_datasets.py
```

It needs Python 3.11 or newer and nothing else.

## Adding a dataset

1. Put the files under `Data/`. Give a dataset with more than one file its own
   directory.
2. Establish where the data came from and what its terms are, from the source
   itself. See [Establishing where a dataset came from](#establishing-where-a-dataset-came-from).
3. Add a `[[dataset]]` block to `DATASETS.toml`, in alphabetical order by
   `name`.
4. If the licence is not already declared in the file, add a `[license.*]`
   table for it and put the full licence text in `LICENSES/`.
5. Run the validator.

Do **not** add a `LICENSE`, `README`, `CITATION` or `.license` file under
`Data/`. Those are rejected by CI. Everything they used to hold has a field in
`DATASETS.toml`: the source goes in `source_url`, the credit line in
`attribution`, the processing you applied in `modification`, the citation in
`references`, and anything else in `notes`.

## What a block looks like

```toml
[[dataset]]
name = "grey_nurse_shark"
title = "Grey nurse shark"
description = "Triangulated surface mesh of a grey nurse shark, in STL format."
path = ["grey_nurse_shark/**"]
SPDX-License-Identifier = "CC-BY-SA-3.0"
provenance = "verified"
source_url = "https://www.thingiverse.com/thing:137954"
source_title = "Thingiverse thing:137954"
collection = "thingiverse"
authors = ["Autodesk"]
attribution = "Grey Nurse Shark, uploaded by rogerpeng1 (https://www.thingiverse.com/thing:137954), licensed under CC BY-SA."
redistributed_from = "https://gitlab.kitware.com/vtk/vtk-examples/-/blob/master/src/Testing/Data/thingiverse/Grey_Nurse_Shark.stl"
notes = "The page's `rel=\"license\"` link names creativecommons.org/licenses/by-sa/3.0/. The uploader disclaims authorship: \"This is a scan by Autodesk obtained from the Autodesk 123D site\"."
```

A simple one is much shorter:

```toml
[[dataset]]
name = "hdr_textures"
title = "HDR environment textures"
description = "High dynamic range equirectangular environment maps of a night sky over Dikhololo and of a parched canal."
path = ["dikhololo_night_4k.hdr", "parched_canal_4k.hdr"]
SPDX-License-Identifier = "CC0-1.0"
provenance = "verified"
source_url = "https://polyhaven.com/a/dikhololo_night"
source_title = "Poly Haven"
attribution = "Poly Haven, https://polyhaven.com/. Attribution is a courtesy, not a requirement under CC0."
```

## Field reference

### Required

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Unique identifier, lowercase letters, digits and underscores. Downstream tools look datasets up by this. |
| `title` | string | Short human-readable name, shown as the gallery card heading. |
| `description` | string | One or two sentences about what the data *is*. Describe the data, not the PyVista function that loads it. |
| `path` | array of strings | Paths relative to `Data/`. Every file must be claimed by exactly one dataset. See [Path patterns](#path-patterns). |
| `SPDX-License-Identifier` | string | An [SPDX expression](https://spdx.org/licenses/), or a `LicenseRef-*` identifier for terms SPDX does not list. Must resolve to a `[license.*]` table. |
| `provenance` | string | `"verified"`, `"inferred"` or `"unknown"`. See below. |

### Conditionally required

| Field | Required when |
| --- | --- |
| `source_url` | Always, unless `provenance = "unknown"`. |
| `attribution` | The licence's `attribution_required` is `true`. |
| `modification` | `modified = true`. |
| `notes` | `provenance` is not `"verified"`, or the licence is `LicenseRef-Unknown`. |

### Optional

| Field | Type | Meaning |
| --- | --- | --- |
| `SPDX-FileCopyrightText` | array of strings | Copyright notices, in [REUSE](https://reuse.software) form. |
| `source_title` | string | Human-readable name of the source, shown next to the link. |
| `collection` | string | Key into a `[collection.*]` table, for upstreams that several datasets share. |
| `authors` | array of strings | Who made the data. |
| `redistributed_from` | string | URL of an intermediate redistributor, when the file reached this repository through one. |
| `modified` | boolean | Whether the file differs from what the source published. |
| `references` | array of tables | Papers to cite: `{ citation = "...", doi = "...", url = "..." }`. `citation` is required, the rest optional. |

## Choosing a `provenance` value

This field says how confident the record is about **where the data came from**.
It says nothing about the licence: the licence's status is carried by
`SPDX-License-Identifier`, and `LicenseRef-Unknown` is how a dataset says its
terms could not be established. The two are independent — the Laser Design
scans have `provenance = "verified"` and `SPDX-License-Identifier =
"LicenseRef-Unknown"`, because the source is certain and publishes no terms.
Anything rendering a badge from this file should take "can I use this?" from
the licence, not from `provenance`.

- **`"verified"`** — you opened the source page and it states where the data
  came from. Most new contributions should be this.
- **`"inferred"`** — the origin is a reasoned conclusion rather than something
  the source states, so say what you inferred and why in `notes`.
- **`"unknown"`** — the origin could not be established. Use
  `SPDX-License-Identifier = "LicenseRef-Unknown"` with it, and say in `notes`
  what you did establish, what you could not, and what a downstream user should
  do.

A new dataset should not normally be `"unknown"`. The existing `"unknown"`
entries are historical: files inherited before this repository recorded
provenance. If you cannot establish where a dataset came from, do not add it.

## Establishing where a dataset came from

Every claim in `DATASETS.toml` is meant to be reproducible by someone who has
only this repository and a network connection. Record what you checked in
`notes`, so the next person can re-run it rather than re-derive it.

**The source is the source.** A licence stated in a docstring, a README, a
sidecar file or a previous version of this table is hearsay, not evidence.
Several entries here were wrong for years because each of those was copied
forward without anyone opening the page: the Nefertiti scan was recorded
non-commercial when its authors publish it under CC BY-SA 4.0, and the cow was
recorded under the collection's BSD-3-Clause when the file itself carries a
clause forbidding resale.

These are the techniques that have actually resolved entries here, roughly in
order of how often they work.

### Read the bytes

More files carry their own provenance than you would expect, and it outranks
anything written about them:

```bash
head -c 400 Data/cow.obj                 # OBJ, PLY, STL and PDB carry comment headers
strings Data/sphere_points.vdb | head    # creator strings in binary formats
exiftool Data/puppy.jpg                  # camera, capture date
python -c "from PIL import Image; print(Image.open('Data/Tango/TangoIcons.png').text)"
unzip -l Data/OpenFOAM.zip               # archives often ship their own LICENSE or README
```

`cow.obj` states a copyright and a no-resale clause. `3GQP.pdb` names its
depositors. `TangoIcons.png` carries its author in a PNG text chunk. The
`nefertiti.ply` header says VTK wrote it, which is how the conversion was
recorded.

### Identify the file, not just the dataset

A filename is often an accession or catalogue number that settles the licence
outright — `3GQP.pdb` is a Protein Data Bank accession, and the whole archive
is CC0. Distinctive dimensions, point counts or array names are searchable
too: `frog_tissues.vti` was matched to its source by dimensions, spacing and
array name together.

### Compare bytes against the upstream

Git's blob hash is the cheapest way to prove two files are the same, and it
works across repositories without downloading either one in full:

```bash
git hash-object Data/skybox2-negx.jpg
git -C ../VTKExamples ls-tree -r HEAD src/Testing/Data/Skyboxes/ | grep negx
```

That is how `skybox2` was traced to the VTK Examples import, and how twelve
groups of byte-identical files were found carrying two different licences.
`tools/validate_datasets.py` now checks the last case on every pull request.

### Check a URL through an API, not a plain request

Several hosts answer `403` to scripts, which looks like "blocked" and hides a
genuine `404`. One dead `source_url` survived three review passes on 65
entries for exactly this reason:

```bash
curl -sS -o /dev/null -w '%{http_code}
' https://gitlab.kitware.com/vtk/vtk-data
#   403 -- tells you nothing
curl -sS -o /dev/null -w '%{http_code}
' \
  https://gitlab.kitware.com/api/v4/projects/vtk%2Fvtk-data
#   404 -- the project does not exist
```

gitlab.kitware.com, codeberg, sketchfab, thingiverse, si.edu and zenodo all
need either their API or a browser user-agent. When a page is gone, the
Wayback Machine usually still has it:

```bash
curl -sS "http://archive.org/wayback/available?url=thingiverse.com/thing:1541337"
```

### Read the version out of the licence link

A page that says "Creative Commons - Attribution" has not told you the
version, and the version changes the terms. Thingiverse encodes it in
`rel="license"` on older pages and in schema.org JSON-LD on newer ones, and
the label-to-version mapping changed over time — the same wording meant 3.0 in
2016 and 4.0 by 2021. Inferring from the upload date gets it wrong; reading
the link gets it right.

```bash
curl -sSL "http://web.archive.org/web/2017/https://www.thingiverse.com/thing:1541337" \
  | grep -o 'rel="license"[^>]*'
```

### When you cannot establish it

Say so. `SPDX-License-Identifier = "LicenseRef-Unknown"` with `notes`
describing what you did establish, what you could not, and what a downstream
user should do is a complete, useful record. A guess dressed as a fact is not,
and it is worse than the gap because nobody re-checks it.

## Path patterns

`path` values are matched against paths relative to `Data/`, with `/` as the
only separator. Downstream tools resolve a file to its dataset with these
rules, so they are part of the format rather than an implementation detail:

| Pattern | Matches |
| --- | --- |
| `bunny.ply` | that one file |
| `skybox/*.jpg` | the `.jpg` files directly in `skybox/`, not in subdirectories |
| `skybox/**` | everything under `skybox/`, at any depth |
| `sim_?.vtu` | `sim_1.vtu` but not `sim_12.vtu`, and never across a `/` |

`*` and `?` stop at a separator; only `**` crosses one. Prefer an explicit file
list when a dataset has a handful of files, and `dir/**` when it owns a whole
directory — `dir/*` will not claim files added in a subdirectory later, and the
validator will report them as uncovered.

## Licence requirements

A new dataset needs a licence that permits redistribution from this repository
and from PyVista, which is MIT. The root `LICENSE` here is Apache-2.0 and
covers the tooling and the imported VTK Examples material, not `Data/`. It normally also needs to
permit commercial use. Non-commercial licences
(CC BY-NC and its variants, "research use only", "personal use only") are
accepted only with explicit maintainer approval, and their `[license.*]` table
must record `commercial_use = false` so the gallery can flag them.

ShareAlike licences (CC BY-SA, ODbL) are accepted, but record
`share_alike = true` and say so in `notes`: a downstream user who derives new
work from the dataset inherits the obligation.

Read the licence out of the page rather than off its label. A Thingiverse page
shows a version-less "Creative Commons - Attribution", but names the version in
its `rel="license"` link (2016-era pages) or its schema.org JSON-LD (2021 and
later) — and the mapping changed over time, so the upload date is not a
substitute. When the live page is a JavaScript shell, read an archived capture.

Prefer CC0 and public-domain sources. [Smithsonian Open Access](https://3d.si.edu/cc0),
[Poly Haven](https://polyhaven.com/) and US government works are all good
places to look.

## Adding a licence

If your dataset's licence is not already in `DATASETS.toml`:

```toml
[license."CC-BY-4.0"]
title = "Creative Commons Attribution 4.0 International"
url = "https://creativecommons.org/licenses/by/4.0/"
commercial_use = true
attribution_required = true
share_alike = false
file = "LICENSES/CC-BY-4.0.txt"
```

Put the full text at the path `file` names. For an SPDX licence, copy it from
the [SPDX license list](https://github.com/spdx/license-list-data/tree/main/text).
For terms that SPDX does not list, use a `LicenseRef-` identifier and write the
text yourself, quoting the source's own words.

The table keys are quoted because SPDX identifiers contain dots, which are
table separators in bare TOML keys.

## Reporting a licence concern

If a dataset here is recorded under incorrect or insufficient terms, or if you
can identify the origin of one of the `LicenseRef-Unknown` entries, please
[open an issue](https://github.com/pyvista/data/issues).
