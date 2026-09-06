# Contributing a dataset

Every file under `Data/` is described by exactly one `[[dataset]]` block in
[`DATASETS.toml`](DATASETS.toml). That file is the single source of truth for
what each dataset is, where it came from and how it may be used. PyVista reads
it and publishes it in the [Dataset Gallery](https://docs.pyvista.org/api/examples/dataset-gallery),
so anything you record here is shown to everyone who downloads the data.

`tools/validate_datasets.py` checks the file on every pull request. Run it
yourself before pushing:

```bash
python tools/validate_datasets.py
```

It needs Python 3.11 or newer and nothing else.

## Adding a dataset

1. Put the files under `Data/`. Give a dataset with more than one file its own
   directory.
2. Add a `[[dataset]]` block to `DATASETS.toml`, in alphabetical order by
   `name`.
3. If the licence is not already declared in the file, add a `[license.*]`
   table for it and put the full licence text in `LICENSES/`.
4. Run the validator.

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
provenance = "inferred"
source_url = "https://www.thingiverse.com/thing:137954"
source_title = "Thingiverse thing:137954"
collection = "thingiverse"
authors = ["rogerpeng1"]
attribution = "Grey Nurse Shark by rogerpeng1 (https://www.thingiverse.com/thing:137954), licensed under CC BY-SA."
redistributed_from = "https://gitlab.kitware.com/vtk/vtk-examples/-/blob/master/src/Testing/Data/thingiverse/Grey_Nurse_Shark.stl"
notes = "The Thingiverse page states \"Creative Commons - Attribution - Share Alike\" without a version. CC BY-SA 3.0 is recorded here because the model was published on 22 August 2013, before CC 4.0 was finalised."
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
source_url = "https://polyhaven.com/"
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
| `path` | array of strings | Paths relative to `Data/`. `dir/**` matches everything under `dir/`. Every file must be claimed by exactly one dataset. |
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

This field says how confident the record is, so downstream users can tell a
researched entry from a guess.

- **`"verified"`** — you opened the source page and it states the origin and the
  terms. Most new contributions should be this.
- **`"inferred"`** — the origin is a reasoned conclusion rather than something
  the source states. A Thingiverse page that says "Creative Commons -
  Attribution" without a version is inferred, not verified. Say what you
  inferred and why in `notes`.
- **`"unknown"`** — the origin could not be established. Use
  `SPDX-License-Identifier = "LicenseRef-Unknown"` with it, and say in `notes`
  what you did establish, what you could not, and what a downstream user should
  do.

A new dataset should not normally be `"unknown"`. The existing `"unknown"`
entries are historical: files inherited before this repository recorded
provenance. If you cannot establish where a dataset came from, do not add it.

## Licence requirements

A new dataset needs a licence that permits redistribution from a BSD-licensed
project, and normally one that permits commercial use. Non-commercial licences
(CC BY-NC and its variants, "research use only", "personal use only") are
accepted only with explicit maintainer approval, and their `[license.*]` table
must record `commercial_use = false` so the gallery can flag them.

ShareAlike licences (CC BY-SA, ODbL) are accepted, but record
`share_alike = true` and say so in `notes`: a downstream user who derives new
work from the dataset inherits the obligation.

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
