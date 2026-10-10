# Where the files in this repository have actually come from

Every source below resolved at least one record. For each: how to recognise
a file from it, how to prove the match, and what its terms are worth.

## The inherited collections

### VTK Data (data.kitware.com, the 2013 VTKData fork)

- Recognise: the file is in `git ls-tree -r --name-only 8f60d72` (the fork
  point) and its history predates 2019-03-09. The Girder collection is
  `https://data.kitware.com/#collection/55f17f758d777f6ddc7895b7`; items
  carry sha512 but no description or provenance.
- Prove: `shasum -a 512` against VTK's content link
  `Testing/Data/<name>.sha512` in `vtk/vtk` (gitlab.kitware.com; the API is
  `https://gitlab.kitware.com/api/v4/projects/vtk%2Fvtk/repository/files/Testing%2FData%2F<name>.sha512/raw?ref=master`).
  `git log` in this repository is the real VTKData history back to 1999, so
  the commit that added the file names the Kitware author and the date;
  VTK's own commit of the same day often names the test that used it.
- Terms: Kitware's `Copyright.txt` is BSD-3-Clause and covers Kitware's own
  work only. Third-party content inside VTK Data (Viewpoint models, the
  teapot, headsq, the frog, Scripps' iron protein, Cyberware scans, the
  Tango icons, Emil Persson's skybox) keeps its own terms, usually written in
  a `readme.txt` beside the files or in the file header. Look for that
  readme before accepting the collection licence.
- Collection table: `collection = "vtk-data"`.

### VTK Examples (lorensen/VTKExamples, now vtk/vtk-examples)

- Recognise: arrived in commit 74bf994 (2019-04-23, "merge data files from
  lorensen/VTKExamples"), 243 files.
- Prove: blob hash against `lorensen/VTKExamples` (`git ls-tree -r HEAD
  src/Testing/Data` in a blob-less clone, or the GitHub trees API);
  `vtk/vtk-examples` keeps the same files in LFS, whose pointer files carry
  sha256 and size. Lorensen's commit messages ("ENH: Add OBJImporter and
  test data") and his examples' `.md` pages sometimes name the source or
  link the forum thread the data came from.
- Terms: Apache-2.0 is the repository's and does not reach third-party data.
- Collection table: `collection = "vtk-examples"`.

### The VTK textbook

- `vtk/vtk-examples` ships the book at `src/VTKBook/*.md`
  (`https://gitlab.kitware.com/api/v4/projects/vtk%2Fvtk-examples/repository/files/src%2FVTKBook%2F<NN>Chapter<NN>%2Emd/raw?ref=master`,
  rendered at `https://examples.vtk.org/site/VTKBook/`). Figure captions
  credit data owners; section 1.11 points to per-directory READMEs for terms.
- Kitware's textbook data distribution at
  `https://vtk.org/vtk-textbook-examples-and-data/` (`README.txt`,
  `PineRoot.tgz` and others, dated 2003-03-17, archived since 2006) is where
  "CD-ROM only" data turned out to be publicly downloadable. Its README grants
  the VTK authors' BSD terms over the distribution; that is the
  redistributor's notice, not the data owner's.

## Repositories and platforms seen more than once

| Source | Recognise | Prove | Terms |
| --- | --- | --- | --- |
| `pyvista/pyvista` and `pyvista-support` issues | commit message or loader docstring names a PR or issue | `gh api -X GET repos/.../issues/<n>/comments`; download `github.com/<org>/<repo>/files/<id>/<name>` and `cmp` | a reply is permission to include, not a licence; a PR author's own generated file takes the repository licence |
| `banesullivan/*` repositories | pyvista-era geoscience files, Transform 2021 notebooks | blob hash via the trees API | his MIT covers his work; look past it for the survey or model owner |
| Laser Design (`laserdesign.com/sample-files/`) | STL/OBJ/PLY header "File exported by Artec Group 3D Scanning Solutions" or "STL Output from geomagic Studio"; pyvista's 2019 loaders fetched from `3dgallery.gks.com` | current pages serve through `laserdesign.sharefile.com/d-s...` shares that can be listed and hashed; case-study posts give date and client | publishes none; site terms are CyberOptics boilerplate; scans commissioned by third parties may not be Laser Design's to grant. `collection = "laser-design"`, `LicenseRef-Unknown` |
| Thingiverse | `thing:<id>` | page or Wayback capture; version from `rel="license"` (2016) or JSON-LD (2021+) | CC, version as read |
| Sketchfab | model id in a URL | `https://api.sketchfab.com/v3/models/<id>` (counts, license, user, createdAt); `?user=<name>` lists an account | the uploader's badge binds only if the uploader is the owner; check the account's other uploads and look for earlier uploads of the same mesh |
| Wikimedia Commons | photographs with no recorded source | `w/api.php?action=query&list=allimages&aisha1=<sha1>` then `prop=imageinfo&iiprop=extmetadata` | licence template on the file page; dual licences at the licensee's choice |
| Poly Haven, Smithsonian Open Access, PDB, US government | named on the page or by accession | page or accession | CC0 or public domain |
| GGG-BenchmarkSfM (Mendeley), Stanford scanning repository, Utah FORGE GDR, Open SciVis | named upstreams with their own pages | hash or inner-volume comparison (Open SciVis volumes are the raw bytes; ours may be zero-padded) | as stated; Stanford's is research-only; Open SciVis repeats the original credit without terms |
| SimScale public projects | `fea/` results with a SimScale screenshot | project page JSON (`ownerName`, parent project) | `LicenseRef-SimScale-PublicProject` only for customer community content; projects owned by the `simscale` account are not covered |
| GrabCAD | SimScale descriptions citing a challenge | challenge results page names winners | ToS grants non-commercial internal use only; no redistribution |
| ECMWF products | netCDF with `grib_to_netcdf` history or int16 `scale_factor` 1.525948758640685e-05 | decode check: every value equals `float32(k) * scale + offset` | ECMWF or Copernicus terms by product; the file alone does not say which product |
| Theses and institutional repositories | handles `hdl.handle.net/<prefix>/<id>` | DSpace API `/server/api/core/items/<uuid>` gives `dc.rights`; bitstreams can be range-downloaded and hashed | "Copyright retained by the author" is not a data licence |
| OnScale, pyBERT/pyGIMLi, PyMAPDL, LaGriT | array names and QA records name the solver | regenerate from the published example and compare geometry when the output itself is not published | the example's code licence covers the script, not its results |

## Query patterns that worked

```bash
# GitHub, read-only: the gate allows these without a named account
gh api -X GET search/code -f q='"sparsePoints.txt"' --jq '.items[] | "\(.repository.full_name) \(.path)"'
gh api -X GET 'search/issues?q=repo:pyvista/pyvista+notch_stress'
gh api -X GET repos/<o>/<r>/git/trees/HEAD -F recursive=1 --jq '.truncated, (.tree[] | select(.sha=="<blob>") | .path)'
gh api -X GET repos/<o>/<r>/commits -F path=<path> --jq '.[-1] | .sha, .commit.author.name, .commit.author.date'

# GitLab
curl -sS 'https://gitlab.kitware.com/api/v4/projects/vtk%2Fvtk/repository/commits?path=Testing/Data/can-vtu.hdf.sha512'

# Wayback
curl -sS 'http://archive.org/wayback/available?url=www.earthmodels.org/data-and-tools/topography/etopo&timestamp=2019'
curl -sS 'http://web.archive.org/cdx/search/cdx?url=scan.laserdesign.com/*&output=json&fl=timestamp,original,statuscode&collapse=urlkey'
curl -sSL -o cap.bin 'http://web.archive.org/web/20220809100945id_/https://www.earthmodels.org/date-and-tools/topography/etopo/etopo_10min_ice.vtp'
head -c "$(stat -f %z cap.bin)" Data/EarthModels/ETOPO_10min_Ice.vtp | cmp - cap.bin   # prefix compare

# Content hashes
curl -sS "https://sources.debian.org/api/sha256/?checksum=$(shasum -a 256 Data/x | cut -c1-64)"
curl -sS "https://commons.wikimedia.org/w/api.php?action=query&list=allimages&aisha1=$(shasum Data/puppy.jpg | cut -c1-40)&format=json"
curl -sS https://api.sketchfab.com/v3/models/8a7e15bbd267476e813e416d6d348f9a | python3 -m json.tool

# The repository file without a full checkout (blob-less clone)
git cat-file blob HEAD:Data/<path> | shasum -a 256
git ls-tree -l HEAD Data/<path>
```

## Hosts that lie to scripts

Checked 2026-09-28 and 2026-10-09. gitlab.kitware.com and zenodo.org answer
200 to plain curl and 403 to a browser user agent; 3d.si.edu answers 403 to
both; cyberoptics.com refuses scripted requests (read the Wayback capture);
thingiverse.com and sketchfab.com answer 200 to both but render as
JavaScript shells; multiaxismetrology.com, 3dgallery.gks.com, volvis.org,
omicron.cs.unc.edu and scan.laserdesign.com no longer resolve. The Wayback
Machine itself flaps between working and "Temporarily Offline" for hours;
retry rather than conclude.
