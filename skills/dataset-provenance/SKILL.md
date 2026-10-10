---
name: dataset-provenance
description: Establish where a file under Data/ came from, who holds the rights and what its terms are, and write the [[dataset]] record in DATASETS.toml that makes the Validate dataset metadata job pass. Use when CI reports an uncovered file, when a new dataset is added, when a record carries LicenseRef-Unknown or provenance = "inferred" or "unknown" and someone asks to resolve it, or when a recorded source is challenged.
---

# Dataset provenance

The job is to answer three questions with evidence a stranger can rerun, then
write the answers into `DATASETS.toml`: **what is this file**, **where did it
come from** (the whole route, not just the last hop), and **what are its
terms**. `CONTRIBUTING.md` is normative for the format and the field
semantics; this skill is the method. Read `CONTRIBUTING.md` sections
"Field reference", "Choosing a provenance value" and "Establishing where a
dataset came from" before the first record.

## Rules that decide every record

These were settled by the maintainer and do not get re-litigated.

1. **The source is the source.** A docstring, a README, a sidecar, a loader
   comment, a pull request body or an earlier version of the table is hearsay.
   Open the page, read the bytes, quote the sentence.
2. **A redistributor's collection licence never covers third-party work.**
   Kitware's BSD notice for VTK Data, the Apache-2.0 of the VTK Examples, a
   GitHub repository's LICENSE, SimScale's terms, Sketchfab's licence badge:
   each covers what that party made. A file they merely host keeps its own
   terms. A repository LICENSE counts only when the file's author committed it
   there (check `git log --diff-filter=A` upstream).
3. **Only the rights holder's terms count.** A forum reply saying "sure, use
   it" is permission to include, not a licence. A platform's terms of service
   are not a licence stated by the author beside the file. A reseller's or
   mirror's CC badge is not the owner's grant.
4. **Found source, no terms: `LicenseRef-Unknown` with `provenance =
   "verified"`** and the origin link. Found terms: record them. Nothing found:
   `provenance = "unknown"`, no `origin_url`, notes saying what was tried.
   `provenance` is about the origin only; the licence carries its own status.
5. **Contributor-made files** (a mesh the PR author generated, a script output
   published in the PR) take the repository licence with a notes sentence
   saying so.
6. **Every fact lives in this table.** PyVista only displays it. Do not leave
   a fact in a docstring or a reader override.
7. **Never print patient identifiers** from medical files (`Data/mr.001`,
   DICOM headers, any file with `PatientName`). Do not run `strings` over all
   of `Data/`; run it on the one file under study.
8. **Byte identity beats a name match.** A same-named file at a candidate
   origin is a lead; a hash match is evidence. Say which one you have.

## Procedure

### 0. Read the failure

```bash
python tools/validate_datasets.py
```

It names the uncovered files, forbidden sidecars (`LICENSE`, `README`,
`CITATION` and friends under `Data/` are rejected; their content moves into
fields), schema errors, ordering errors and byte-identical files whose
records disagree. Fix the schema errors last; they are mechanical.

### 1. Identify the file from its own bytes

Highest yield of any step. Do this before any search.

```bash
f=Data/<path>
file "$f"; ls -l "$f"; git hash-object "$f"; shasum -a 256 "$f"; shasum -a 512 "$f"
head -c 600 "$f"                      # OBJ, PLY, STL, VTK legacy, PDB, MHD, NRRD headers
strings -n 8 "$f" | head -40          # creator strings, software names, QA records in binary formats
exiftool "$f"                         # images: camera, date, copyright, software
python3 -c "from PIL import Image; print(Image.open('$f').text)"   # PNG tEXt chunks
unzip -l "$f"; tar tzvf "$f"          # archives: member names, dates, nested READMEs, __MACOSX stamps
python3 - <<'EOF'                     # netCDF, HDF5, VTK XML: attributes and array names
import sys; import netCDF4, h5py       # whichever applies
EOF
```

What to extract and why it matters:

- **Creator strings.** "Golden Software ioVtk.dll", "Artec Group 3D Scanning
  Solutions", "meshio 3.3.1", "Blender v2.66 OBJ File: 'doorman.blend'",
  "Noesis .obj export", "vtkXMLWriter", "FSL3.2beta", "grib_to_netcdf".
  Each names a toolchain and often the publisher.
- **Exodus QA and Info records** name the simulation codes, run date and
  input decks (FASTQ, Gen3D, PRONTO3D, "self contact test problem" settled
  `can.ex2` as Sandia's).
- **Dimensions, spacing, origin, point and face counts.** A MetaImage header
  has no array name, but `DimSize = 500 470 136` is searchable and matched
  LBNL's frog. Vertex and face counts matched the tiger fighter to Sketchfab.
- **Array names** carry the writer: `SLCImage` is vtkSLCReader; `_Marker` and
  `_Attribute` are pyGIMLi; `vtkOriginalCellIds` is a ParaView extraction;
  `Nodal Stress-0` is pyvista's component plotting.
- **Accession and catalogue numbers in filenames.** `3GQP.pdb` is a PDB
  accession and the archive is CC0; `GSE14929`, `SRA008712`, a Thingiverse
  `thing:` id, a Sketchfab model id, a handle `11124/...` settle the origin.
- **Dates.** EXIF capture time, zip member dates, `__MACOSX` quarantine
  stamps, QA run dates. A date earlier than every known redistribution is a
  lead for the search and a sanity check on candidates.
- **Patient or person data.** Stop, do not print it, record that it exists and
  which tags, and flag it (see `Data/mr.001` in the table for the wording).

### 2. Date the arrival and read the discussion

```bash
git log --diff-filter=A --follow --format='%h %ad %an %s' --date=short -- "$f"
git show <sha> --stat
git ls-tree -r --name-only 8f60d72 | grep <name>     # was it in the 2013 VTKData fork?
```

Two dates split the inherited history: before 2019-03-09 the file is from
VTKData; commit 74bf994 (2019-04-23) merged 243 files from
`lorensen/VTKExamples`; everything later is pyvista-era and usually traceable
through the commit message, a `pyvista/data` pull request, a `pyvista/pyvista`
pull request or issue, or a `pyvista-support` issue.

Then read the **whole** discussion, comments and attachments included. The
sentence that names the source is in a comment more often than in the body,
and attachments (`files/NNN/x.zip`) are what the bytes should be compared to.

```bash
gh api -X GET repos/pyvista/pyvista/issues/<n>/comments --jq '.[] | "\(.user.login) \(.created_at): \(.body)"'
gh api -X GET 'search/issues?q=repo:pyvista/pyvista+<filename>'
gh api -X GET repos/pyvista/pyvista/pulls/<n>/files --jq '.[].filename'
```

Also search the pyvista source history for the loader: the first
`download_<name>` docstring often cites the URL it fetched from, and the
pyvista commit that added it is dated.

```bash
git -C ~/dev/pyvista log -S'<filename>' --format='%h %ad %s' --date=short | tail -3
```

### 3. Find the origin

Work the veins in this order; stop when the bytes match or the source states
the origin.

1. **Blob hash against known upstreams.** Cheapest proof there is.
   `git hash-object` the file, then `git ls-tree -r HEAD` in a
   `--filter=blob:none --no-checkout` clone of the candidate, or the GitHub
   trees API (`repos/{o}/{r}/git/trees/HEAD?recursive=1`, check
   `truncated`). Candidates: `lorensen/VTKExamples`,
   `vtk/vtk-examples` on gitlab.kitware.com (LFS pointers carry sha256 and
   size), `vtk/vtk` content links (`Testing/Data/<name>.sha512`),
   `banesullivan/*`, `pyvista/pyvista-support` attachments, the PR author's
   own repositories. See `references/sources.md` for the full list.
2. **Code search on the distinctive filename or string.**
   `gh api -X GET search/code -f q='"<filename>"'` (quota is 10 per minute
   shared across agents; one query per distinctive token). grep.app is behind
   a bot challenge; Software Heritage needs a token.
3. **Content-hash indexes.** `https://sources.debian.org/api/sha256/?checksum=<sha256>`
   for anything that ever shipped in a Debian package;
   `https://commons.wikimedia.org/w/api.php?action=query&list=allimages&aisha1=<sha1>&format=json`
   for images (this is how `puppy.jpg` was found); Sketchfab's API for mesh
   counts (`https://api.sketchfab.com/v3/models/<id>` gives vertexCount,
   faceCount, license, user, createdAt).
4. **The VTK textbook and VTK's own sources.** The book ships inside
   `vtk/vtk-examples` at `src/VTKBook/*.md` and credits data in figure
   captions ("courtesy of Scripps Clinic", "generated by Janet MacFall at the
   Center for In Vivo Microscopy"); Kitware's textbook data archive at
   `https://vtk.org/files/VTKTextbook/` (`README.txt`, `PineRoot.tgz` and
   others, dated 2003) is where several "no source" files turned out to be
   publicly downloadable. VTK test comments, `Testing/Data/*/readme.txt`
   files beside the data and `git log` of the content link say what Kitware
   knew.
5. **Web search by title, author, instrument, place and date.** Laser Design
   case studies, GrabCAD challenge results, university course pages, thesis
   repositories (handles), conference tutorials, data-availability
   statements in the paper the dataset illustrates. Search the distinctive
   number too (a grid size, a vertex count, a UUID in a filename).
6. **The Wayback Machine, through its APIs.** Availability:
   `http://archive.org/wayback/available?url=<url>&timestamp=<yyyymmdd>`;
   CDX for every capture of a host: `http://web.archive.org/cdx/search/cdx?url=<host>/*&output=json&fl=timestamp,original,statuscode&limit=2000`;
   exact bytes with `id_`: `http://web.archive.org/web/<ts>id_/<url>`.
   Captures of large files are truncated to a 1 MiB or 5 MiB prefix, so
   compare prefixes with `cmp` and say so. An empty availability answer is
   not final; try CDX and a dated redirect. The service goes offline for
   hours at a time; retry later rather than concluding.
7. **Ask the host's API, never a plain request.** gitlab.kitware.com,
   zenodo, sketchfab, thingiverse, si.edu, cyberoptics answer scripts
   differently from browsers, which hides real 404s. `curl -sSI` then the
   JSON API. When a page is a JavaScript shell, read an archived capture.

### 4. Establish the terms

Only once the origin is known. In order of authority:

1. A licence published beside the file by its author: a `readme.txt` next to
   the data upstream, a `LICENSE` committed by the author, a dataset landing
   page's licence field, a Commons file page's licence template, a PDB or
   Poly Haven blanket dedication.
2. A licence stated on the publishing page. Read the **version** out of
   `rel="license"` or the schema.org JSON-LD, not the label; Thingiverse's
   "Creative Commons - Attribution" meant 3.0 in 2016 and 4.0 by 2021.
3. The owner's stated terms for a whole archive, when the file is shown to
   be in it (Cyberware's 2001 samples page, UNC's CHVRTD notice, CIVM's
   Shared Data page). Scope matters: a statement about "data on this site"
   does not reach a file not shown to be on the site. Record it as a lead,
   keep `LicenseRef-Unknown`, and name the identifier it would become.
4. A journal's data-availability statement covers the deposited data, not a
   derived file, and an open-access article licence covers the paper only.

What does **not** establish terms: a GitHub repository LICENSE over a file
the author did not commit; a platform ToS (Discourse CC BY-NC-SA, SimScale
community content, GrabCAD cross-licence); a site's boilerplate terms of use;
a textbook "courtesy of" credit; a reseller's CC badge; a tutorial page
footer. Record each of these in notes as what it is, so the next person does
not re-derive it, and keep the identifier undetermined.

Map the result to an identifier that resolves to a `[license.*]` table; add
a table and the text under `LICENSES/` when it is new (`CONTRIBUTING.md`,
"Adding a licence"). For a dual licence at the licensee's choice, record the
permissive option and say so in notes. Set `attribution` whenever
`attribution_required` is true, in the form the licence asks for.

### 5. Write the record

Follow the shape in `CONTRIBUTING.md`. Beyond the schema:

- `origin_url` is the furthest upstream page that publishes the work, not a
  download link and not the last redistributor. Pin a repository blob URL to
  a commit when the path may move.
- `redistributed_from` is the route **this copy** took, origin first, last
  hop last. A parallel copy elsewhere (a Sketchfab mirror, a thesis-notebooks
  republication) is not a hop; it goes in notes.
- `authors` are the people or body who made the data, from the source's own
  credit. A platform account is a contributor, not an author, unless the page
  says own work.
- `modified = true` with `modification` whenever the bytes differ from what
  the source published; say how (`clean().decimate(0.95)`, "re-saved through
  VTK's XML writer", "mask == 0 set to NaN").
- `notes` is the audit trail: what was checked, the command or URL to rerun
  it, the hash or count that matched, what was not checked and why, and what
  a downstream user should do. Every commit, pull request, issue, discussion
  and page you cite carries its full URL in parentheses, because PyVista
  renders notes and a bare `commit 79f41c7` is not clickable. Hashes may be
  abbreviated with `...` after eight characters. Wrap at 78 columns; an
  indented paragraph renders as a literal block, so indent only commands.
- Style: British "licence" in prose, `LICENSE` only as a filename; plain
  ASCII punctuation, no em or en dashes; describe the record as it stands,
  never the history of the edit.
- Keep `name` first, blocks sorted by name in codepoint order, and split a
  multi-file record when one file has its own origin and terms (bahamas_rgb
  came out of pvgeo_examples this way).

Then:

```bash
python tools/validate_datasets.py
python -m pytest tools -q
```

### 6. Verify adversarially before committing

Before a finding changes `SPDX-License-Identifier`, `provenance` or
`origin_url`, try to refute it as a stranger would:

- Fetch the evidence URL again and confirm the quoted sentence is on the
  page, and that it says what the record claims (a "courtesy of" is not a
  grant; "free for non-commercial use" is not CC BY).
- Check the claim against rules 2 and 3 above. Who committed the LICENSE?
  Is the badge the owner's?
- If the match rests on a name, a count or a date rather than bytes, say so
  in notes and do not promote `provenance` past "inferred" unless the source
  itself states the origin.
- Look for an older copy than the candidate (an earlier upload of the same
  mesh undermined the reseller-as-owner reading of the tiger fighter).
- Check the validator's duplicate-blob rule: a byte-identical file elsewhere
  in `Data/` must agree on licence and provenance.

For more than a handful of records, run the research and the refutation as
separate agents; `references/workflow.md` has the script and the brief.

## Dead ends, so nobody pays for them twice

- VTK Discourse: zero provenance posts across 42 filenames searched.
- Software Heritage without a token (401); grep.app (bot challenge);
  Debian's `vtkdata/debian/copyright` (blanket BSD); Semantic Scholar.
- klacansky.com refuses HTTPS; use `http://`.
- 3dgallery.gks.com (Laser Design's old gallery) is gone and the Wayback
  Machine has only redirects; Laser Design now serves samples through
  ShareFile links that need a name and email, and `laserdesign.sharefile.com`
  shares can be listed and hashed.
- Sketchfab downloads need a login; the v3 API gives counts and licence
  without one.
- GitLab blob search needs auth; clone `--filter=blob:none` instead.
- `labels.mhd`, `earth.ppm`, `banes_heart`, `delaunay_example`, `tree.ply`,
  `reactor.zip`, `hertzian_contact_cylinder`, `kafadar_lidar`, `doorman`,
  `dc_inversion` and the Laser Design terms were worked by several agents
  over several weeks; the notes say exactly what was tried. Only reverse
  image search and Software Heritage with a token remain untried.
- Kitware precedent: it removed `2h2o.out`, the file carrying MOPAC's
  copyright banner, "pending clarification on redistribution". Removal is a
  maintainer decision, not yours; record and flag.

## Reporting

Report per record: what the file is, origin with the evidence type (bytes,
stated, name match), the route, the terms with the sentence that states
them, what changed in the table, and what remains open with the contact to
ask. Nothing is applied to a record on a guess; `LicenseRef-Unknown` with
good notes is a complete, useful answer.
