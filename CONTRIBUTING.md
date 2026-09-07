# Contributing a dataset

Every file tracked under `Data/` is described by exactly one `[[dataset]]` block in
[`DATASETS.toml`](DATASETS.toml). That file is the single source of truth for
what each dataset is, where it came from and how it may be used. PyVista will
read it through `examples.get_example(...)` and publish it in the
[Dataset Gallery](https://docs.pyvista.org/api/examples/dataset_gallery) once
pyvista/pyvista#9118 merges, so anything you record here is shown to everyone
who downloads the data.

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
`DATASETS.toml`: the source goes in `origin_url`, the credit line in
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
origin_url = "https://www.thingiverse.com/thing:137954"
origin_title = "Thingiverse thing:137954"
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
origin_url = "https://polyhaven.com/a/dikhololo_night"
origin_title = "Poly Haven"
attribution = "Poly Haven, https://polyhaven.com/. Attribution is a courtesy, not a requirement under CC0."
```

## Field reference

### Required

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | string | Unique identifier, lowercase letters, digits and underscores. Downstream tools look datasets up by this. |
| `title` | string | Short human-readable name, shown as the gallery card heading. |
| `description` | string | One or two sentences about what the data *is*. Describe the data, not the PyVista function that loads it. |
| `path` | array of strings | Paths relative to `Data/`. Every tracked file except dotfiles must be claimed by exactly one dataset. See [Path patterns](#path-patterns). |
| `SPDX-License-Identifier` | string | An [SPDX expression](https://spdx.org/licenses/), or a `LicenseRef-*` identifier for terms SPDX does not list. Must resolve to a `[license.*]` table. |
| `provenance` | string | `"verified"`, `"inferred"` or `"unknown"`. See below. |

### Conditionally required

| Field | Required when |
| --- | --- |
| `origin_url` | Always, unless `provenance = "unknown"`. |
| `attribution` | The licence's `attribution_required` is `true`. |
| `modification` | `modified = true`. |
| `notes` | `provenance` is not `"verified"`, or the licence is `LicenseRef-Unknown`. |

### Optional

| Field | Type | Meaning |
| --- | --- | --- |
| `SPDX-FileCopyrightText` | array of strings | Copyright notices, in [REUSE](https://reuse.software) form. |
| `origin_title` | string | Human-readable name of the origin, shown next to the link. |
| `collection` | string | Key into a `[collection.*]` table, for upstreams that several datasets share. |
| `authors` | array of strings | Who made the data. |
| `redistributed_from` | string | URL this copy actually came through, when that is not `origin_url`. |
| `modified` | boolean | Whether the file differs from what the source published. |
| `references` | array of tables | Papers to cite: `{ citation = "...", doi = "...", url = "..." }`. `citation` is required, the rest optional. |

### `origin_url` is not a download link

`origin_url` is the furthest upstream point you could establish: the page
that publishes the work and states its terms. It is not where this repository
serves the file from, and it is usually a page about the work rather than a
link to a file.

When the copy here came through somewhere else, `redistributed_from` records
that route and `origin_url` still names the origin. The Stanford bunny's
origin is the Stanford scanning repository; it reached this repository
through the VTK Examples import, and both are written down.

Where the trail runs out at a redistributor, `origin_url` names the
redistributor and `provenance` says `inferred`, because that is genuinely as
far back as anyone got. Many entries are in that position, most of them
pointing at VTK Data or the VTK Examples. Do not dress one of those up as an
originator.

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
too: `froggy/frogtissue.mhd` was matched to its source by dimensions, spacing and
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

### Ask when the file arrived, not when the repository was forked

This repository is a fork of VTKData, but the tree it forked has 756 files in
it, and there are now 1258. A file being here is no evidence at all that it
came with the fork, and nine entries carried a VTK Data licence for exactly
that reason.

```bash
git ls-tree -r --name-only 8f60d72 | grep froggy   # the fork point, July 2013
git log --diff-filter=A --follow --format='%ad %an %s' --date=short -- Data/froggy/frog.mhd
```

The second command dates `froggy` to April 2019 and names the commit that
brought it, "merge data files from lorensen/VTKExamples" — a different
upstream with a different licence.

### Hash against VTK's own content links

VTK does not store its test data in git; it stores a `.sha512` file naming
each object. Those files are the authority on whether something really is VTK
test data, and they are cheap to check in bulk:

```bash
shasum -a 512 Data/DICOMDirectory/mr.001
cat /path/to/VTK/Testing/Data/mr.001.sha512
```

A match proves Kitware distributes that exact file. It does **not** prove the
file is Kitware's to license, and no match, for a file no upstream has, is a
reason to suspect the recorded source.

Before you conclude that a collection's notice covers a file, look for a
`readme` next to it upstream, because that is where the exception is written:

```bash
ls /path/to/VTK/Testing/Data/skybox/          # readme.txt sits beside the six faces
cat /path/to/VTK/Testing/Data/skybox/readme.txt
```

That readme names Emil Persson and CC BY 3.0, and the six faces are
byte-identical to `skybox2-*.jpg` here — which was recorded as Apache-2.0
under the collection's licence for years. VTK carries at least three such
exceptions in sibling files: the Viewpoint cow, the Tango icons and this
skybox. A collection licence is the redistributor's, and it cannot reach a
third party's work.

### Check a URL through an API, not a plain request

Several hosts answer `403` to scripts, which looks like "blocked" and hides a
genuine `404`. One dead `origin_url` survived three review passes on 65
entries for exactly this reason:

```bash
curl -sSI https://gitlab.kitware.com/vtk/vtk-data | head -1
#   HTTP/2 302 -- a redirect to a sign-in page, which tells you nothing

curl -sS https://gitlab.kitware.com/api/v4/projects/vtk%2Fvtk-data
#   {"message":"404 Project Not Found"} -- the project does not exist
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

### Read the whole discussion, not just the pull request body

A file usually arrives through a pull request, and the sentence that says
where it came from is as often in a comment as in the body. `EnSight.zip` was
recorded as VTK data for years; the contributor had said plainly in the issue
that he could find no EnSight sample under an open licence and so converted
one of his own OpenFOAM runs.

```bash
gh api repos/pyvista/pyvista/issues/722/comments --jq '.[] | "\(.user.login): \(.body)"'
```

`wavy.zip` is the same story in the other direction: the pull request that
added it publishes the PyVista script that generated it, which is why it is
recorded as MIT rather than as ParaView's.

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

Every `[license.*]` table records `text_source`: where the text in `file`
came from. For a licence SPDX lists, that is its entry in the SPDX License
List, and the text in `LICENSES/` is the canonical text unchanged. Anyone can
check that for themselves:

```bash
python - <<'EOF'
import json, pathlib, re, urllib.request
ident = 'CC-BY-4.0'
mine = pathlib.Path(f'LICENSES/{ident}.txt').read_text()
with urllib.request.urlopen(f'https://spdx.org/licenses/{ident}.json') as r:
    canon = json.load(r)['licenseText']
norm = lambda t: re.sub(r'\s+', ' ', t).strip().lower()
print('identical' if norm(mine) == norm(canon) else 'DIFFERS')
EOF
```

All twelve SPDX-listed texts here pass that check. The nine `LicenseRef-`
files are not licence texts: SPDX does not list those terms, so each one
states the terms in its own words, names its source at the top, and quotes
the wording it is based on. `text_source` points at that source.


If your dataset's licence is not already in `DATASETS.toml`:

```toml
[license."CC-BY-4.0"]
title = "Creative Commons Attribution 4.0 International"
url = "https://creativecommons.org/licenses/by/4.0/"
commercial_use = true
attribution_required = true
share_alike = false
file = "LICENSES/CC-BY-4.0.txt"
text_source = "https://spdx.org/licenses/CC-BY-4.0.json"
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
