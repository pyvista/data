# Working in pyvista/data with a coding agent

Entry point for any coding agent working in this repository. `CONTRIBUTING.md`
is normative: it defines the `DATASETS.toml` format, the field semantics, the
licence requirements and the techniques for establishing where a file came
from. Where anything here disagrees with it, follow `CONTRIBUTING.md`.

## What this repository is

`Data/` holds the example datasets that PyVista downloads, and `DATASETS.toml`
at the root records what every file is, where it came from, who holds the
rights and what its terms are. `tools/validate_datasets.py` checks that every
tracked file under `Data/` belongs to exactly one `[[dataset]]` record and
that each record is complete; CI runs it and the validator's tests on every
pull request. Installed copies of PyVista read `DATASETS.toml` from `master`,
so a change here is public the moment it merges.

## Skills

Skills are task guides in the open Agent Skills format (`SKILL.md` with
`name` and `description` frontmatter, references beside it). The real files
live under `skills/`; `.claude/skills` and `.agents/skills` are symlinks to
that directory, so Claude Code and Codex each find the same skill in the
place they scan, and any other agent can read it by path. Nothing in them is
specific to one agent.

| Task | Guide |
| --- | --- |
| A file under `Data/` has no record, CI reports it uncovered, a record carries `LicenseRef-Unknown` or an unverified provenance, or a recorded source is challenged | `skills/dataset-provenance/SKILL.md` |

## Rules that apply before you open a guide

- **Never add a `LICENSE`, `README`, `COPYING`, `NOTICE` or `CITATION` file
  under `Data/`**, in any spelling or case, nor a `.license` sidecar. CI
  rejects them; everything they would hold has a field in `DATASETS.toml`.
- **A redistributor's licence never covers third-party work.** Kitware's BSD
  notice, the VTK Examples' Apache-2.0 and a GitHub repository's LICENSE each
  cover what that party made. A file they merely host keeps its own terms.
- **Only the rights holder's terms count.** A forum reply, a platform's terms
  of service or a mirror's licence badge is not a licence for the data.
- **Never print patient identifiers** from medical files. `Data/mr.001`
  carries an identifiable patient's data; its record says how to handle it.
- **Run the validator before you finish**: `python tools/validate_datasets.py`
  and `python -m pytest tools -q`. Do not use CI to find out.
- Prose in this repository uses British spelling (`licence` in prose, `LICENSE`
  only as a filename) and plain ASCII punctuation.
