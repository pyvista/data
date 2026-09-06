#!/usr/bin/env python3
"""Check that DATASETS.toml describes every file under Data/ and is well formed."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASETS_TOML = ROOT / 'DATASETS.toml'
LICENSES_DIR = ROOT / 'LICENSES'
DATA_DIR = 'Data'
SCHEMA_VERSION = 1

DOCS = 'https://github.com/pyvista/data/blob/master/CONTRIBUTING.md'

NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_]*$')
SPDX_RE = re.compile(r'^[A-Za-z0-9.+-]+$')
PROVENANCE = ('verified', 'inferred', 'unknown')
UNKNOWN_LICENSE = 'LicenseRef-Unknown'

DATASET_REQUIRED = ('name', 'title', 'description', 'path', 'SPDX-License-Identifier', 'provenance')
DATASET_OPTIONAL = (
    'SPDX-FileCopyrightText', 'origin_url', 'origin_title', 'collection', 'authors',
    'attribution', 'redistributed_from', 'modified', 'modification', 'notes', 'references',
)
LICENSE_REQUIRED = ('title', 'url', 'file', 'commercial_use', 'attribution_required', 'share_alike')
COLLECTION_REQUIRED = ('title', 'url', 'description')

FORBIDDEN_STEMS = {
    'license', 'licence', 'licenses', 'licences', 'copying', 'copyright',
    'notice', 'notices', 'readme', 'readmes', 'citation', 'citations',
}
FORBIDDEN_SUFFIXES = ('.license',)
DOCUMENT_SUFFIXES = ('', '.txt', '.md', '.rst', '.cff', '.html', '.adoc')


class Problems:
    """Collected validation failures, printed as an actionable report."""

    def __init__(self) -> None:
        self.items: list[tuple[str, str, str]] = []

    def add(self, where: str, what: str, fix: str) -> None:
        """Record one failure with the place, the problem and the remedy."""
        self.items.append((where, what, fix))

    def report(self) -> int:
        """Print every failure and return the process exit status."""
        if not self.items:
            print('DATASETS.toml is valid.')
            return 0
        print(f'DATASETS.toml validation failed with {len(self.items)} problem(s).\n')
        for where, what, fix in self.items:
            print(f'  {where}')
            print(f'    problem: {what}')
            for number, line in enumerate(fix.splitlines()):
                label = '    fix:     ' if number == 0 else '             '
                print(f'{label}{line}')
            print()
        print(f'See {DOCS} for the full format reference and worked examples.')
        return 1


def tracked_data_files() -> list[str]:
    """List every tracked file under Data/, as a path relative to Data/."""
    out = subprocess.run(
        ['git', '-C', str(ROOT), 'ls-files', DATA_DIR],
        capture_output=True, text=True, check=True,
    ).stdout.split('\n')
    return sorted(
        line[len(DATA_DIR) + 1:]
        for line in out
        if line.startswith(DATA_DIR + '/') and not Path(line).name.startswith('.')
    )


def pattern_regex(pattern: str) -> re.Pattern[str]:
    """Compile a path pattern, where `*` stops at a separator and `**` crosses one."""
    out, index = [], 0
    while index < len(pattern):
        char = pattern[index]
        if char == '*':
            if pattern[index + 1:index + 2] == '*':
                out.append('.*')
                index += 2
                continue
            out.append('[^/]*')
        elif char == '?':
            out.append('[^/]')
        else:
            out.append(re.escape(char))
        index += 1
    return re.compile('^' + ''.join(out) + '$')


def matches(pattern: str, path: str) -> bool:
    """Match a REUSE-style path pattern against a path relative to Data/."""
    if pattern.endswith('/**'):
        return path.startswith(pattern[:-2])
    return bool(pattern_regex(pattern).match(path))


def license_terms(expression: str) -> list[str]:
    """Split an SPDX license expression into the license identifiers it names."""
    tokens = [token for token in re.split(r'[()\s]+', expression) if token]
    terms, skip = [], False
    for token in tokens:
        if token.upper() == 'WITH':
            skip = True
        elif token.upper() in {'AND', 'OR'}:
            skip = False
        elif skip:
            skip = False
        else:
            terms.append(token)
    return terms


def is_forbidden(path: str) -> bool:
    """Say whether a path is a per-dataset metadata file that DATASETS.toml replaces."""
    name = Path(path).name.casefold()
    if name.endswith(FORBIDDEN_SUFFIXES):
        return True
    head = re.split(r'[.\-_]', name, maxsplit=1)[0]
    return head in FORBIDDEN_STEMS and Path(name).suffix in DOCUMENT_SUFFIXES


def slugify(text: str) -> str:
    """Turn a file or directory name into a candidate dataset name."""
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_') or 'new_dataset'


def suggested_name(parent: str, members: list[str]) -> str:
    """Suggest a dataset name for a group of uncovered files."""
    return slugify(parent if parent != '.' else Path(members[0]).stem)


def suggested_path(parent: str, members: list[str]) -> str:
    """Suggest a `path` value for a group of uncovered files."""
    if parent != '.' and len(members) > 1:
        return f'["{parent}/**"]'
    return '[' + ', '.join(f'"{member}"' for member in members) + ']'


def check_forbidden_files(files: list[str], problems: Problems) -> None:
    """Reject per-dataset licence, readme and citation files under Data/."""
    for path in files:
        if is_forbidden(path):
            problems.add(
                f'Data/{path}',
                'per-dataset metadata files are not allowed under Data/',
                'Delete this file and put its content in the dataset\'s [[dataset]] block\n'
                'in DATASETS.toml instead: the source in `origin_url`, the licence in\n'
                '`SPDX-License-Identifier`, the required credit in `attribution`, any\n'
                'processing in `modification`, and everything else in `notes`.',
            )


LIST_FIELDS = ('path', 'authors', 'SPDX-FileCopyrightText', 'references')


def check_shape(doc: dict, problems: Problems) -> bool:
    """Check the top-level shape, and say whether the deeper checks can run."""
    ok = True
    for key, kind, shape in (
        ('license', dict, '[license."SPDX-Id"] tables'),
        ('collection', dict, '[collection."name"] tables'),
        ('dataset', list, '[[dataset]] blocks'),
    ):
        value = doc.get(key)
        if value is not None and not isinstance(value, kind):
            problems.add(f'DATASETS.toml `{key}`', f'this is a {type(value).__name__}, not {shape}',
                         f'`{key}` is written as {shape}, not as a bare key. For example:\n'
                         '  [license."CC-BY-4.0"]\n'
                         '  title = "Creative Commons Attribution 4.0 International"')
            ok = False
    for index, entry in enumerate(doc.get('dataset', []) if isinstance(doc.get('dataset'), list) else []):
        if not isinstance(entry, dict):
            problems.add(f'DATASETS.toml [[dataset]] #{index + 1}',
                         f'this is a {type(entry).__name__}, not a table',
                         'Each dataset is a `[[dataset]]` table with `name`, `title` and the rest.')
            ok = False
            continue
        for field in LIST_FIELDS:
            value = entry.get(field)
            if value is None:
                continue
            if not isinstance(value, list):
                problems.add(f'DATASETS.toml [[dataset]] name = {entry.get("name")!r}',
                             f'`{field}` is a {type(value).__name__}, not an array',
                             f'Write `{field}` as an array, even with one element:\n'
                             f'  {field} = ["one-value"]')
                ok = False
                continue
            want = dict if field == 'references' else str
            shape = 'a table' if want is dict else 'a string'
            for element in value:
                if not isinstance(element, want):
                    example = (
                        '  references = [{ citation = "...", doi = "..." }]'
                        if want is dict
                        else f'  {field} = ["one-value", "another"]'
                    )
                    problems.add(f'DATASETS.toml [[dataset]] name = {entry.get("name")!r}',
                                 f'`{field}` holds a {type(element).__name__}, not {shape}',
                                 f'Every entry of `{field}` must be {shape}:\n{example}')
                    ok = False
                    break
    for entry in doc.get('dataset', []) if isinstance(doc.get('dataset'), list) else []:
        if not isinstance(entry, dict):
            continue
        for field in ('name', 'title', 'description', 'SPDX-License-Identifier',
                      'provenance', 'collection', 'origin_url', 'attribution'):
            value = entry.get(field)
            if value is not None and not isinstance(value, str):
                problems.add(f'DATASETS.toml [[dataset]] #{entry.get("name") or "?"}',
                             f'`{field}` is a {type(value).__name__}, not a string',
                             f'Write `{field}` as a plain string:\n  {field} = "one-value"')
                ok = False
    licenses = doc.get('license')
    for key, table in (licenses if isinstance(licenses, dict) else {}).items():
        if not isinstance(table, dict):
            problems.add(f'DATASETS.toml [license.{key}]',
                         f'this is a {type(table).__name__}, not a table',
                         f'Write it as a table:\n  [license."{key}"]\n  title = "..."')
            ok = False
            continue
        if isinstance(table, dict):
            for field in ('commercial_use', 'attribution_required', 'share_alike'):
                value = table.get(field)
                if value is not None and not isinstance(value, bool):
                    problems.add(f'DATASETS.toml [license."{key}"]',
                                 f'`{field}` is a {type(value).__name__}, not a boolean',
                                 f'Write `{field}` as `true` or `false`, unquoted.')
                    ok = False
            if 'file' in table and not isinstance(table['file'], str):
                problems.add(f'DATASETS.toml [license."{key}"]',
                             '`file` is not a string',
                             '`file` is a path to the licence text, such as\n'
                             f'  file = "LICENSES/{key}.txt"')
                ok = False
    return ok


def check_license_tables(doc: dict, problems: Problems) -> None:
    """Check every [license.*] table and the licence text it points at."""
    for key, table in doc.get('license', {}).items():
        where = f'DATASETS.toml [license.{key}]'
        if not SPDX_RE.match(key):
            problems.add(where, f'{key!r} is not a valid licence identifier',
                         'Use an SPDX identifier such as `CC-BY-4.0`, or a custom\n'
                         '`LicenseRef-Something` identifier for terms SPDX does not list.')
        for field in LICENSE_REQUIRED:
            if field not in table:
                problems.add(where, f'missing required key `{field}`',
                             f'Add `{field}` to the [license.{key}] table. See '
                             'an existing licence table for the shape.')
        path = table.get('file')
        if path and not (ROOT / path).is_file():
            problems.add(where, f'`file` points at {path}, which does not exist',
                         f'Add the full licence text at {path}. For an SPDX licence,\n'
                         'copy it from https://github.com/spdx/license-list-data/tree/main/text.')


def check_collection_tables(doc: dict, problems: Problems) -> None:
    """Check every [collection.*] table."""
    for key, table in doc.get('collection', {}).items():
        where = f'DATASETS.toml [collection."{key}"]'
        for field in COLLECTION_REQUIRED:
            if field not in table:
                problems.add(where, f'missing required key `{field}`',
                             f'Add `{field}` to the [collection."{key}"] table.')


def check_dataset(entry: dict, index: int, doc: dict, problems: Problems) -> None:
    """Check one [[dataset]] block against the schema."""
    name = entry.get('name')
    where = f'DATASETS.toml [[dataset]] name = {name!r}' if name else (
        f'DATASETS.toml [[dataset]] #{index + 1}'
    )
    for field in DATASET_REQUIRED:
        if field not in entry:
            problems.add(where, f'missing required key `{field}`',
                         f'Add `{field}`. Every dataset needs: '
                         + ', '.join(f'`{f}`' for f in DATASET_REQUIRED) + '.')
    unknown = set(entry) - set(DATASET_REQUIRED) - set(DATASET_OPTIONAL)
    if unknown:
        problems.add(where, f'unknown key(s): {", ".join(sorted(unknown))}',
                     'Remove the key or correct the spelling. Allowed keys are:\n'
                     + ', '.join(f'`{f}`' for f in DATASET_REQUIRED + DATASET_OPTIONAL) + '.')

    if name is not None and not NAME_RE.match(name):
        problems.add(where, f'`name` {name!r} is not a valid identifier',
                     'Use lowercase letters, digits and underscores, starting with a\n'
                     'letter or digit, for example `grey_nurse_shark`.')

    provenance = entry.get('provenance')
    if provenance is not None and provenance not in PROVENANCE:
        problems.add(where, f'`provenance` is {provenance!r}',
                     'Set `provenance` to one of: '
                     + ', '.join(f'"{p}"' for p in PROVENANCE) + '.\n'
                     '  "verified" - you read the source page and it states the origin\n'
                     '  "inferred" - the origin is a reasoned conclusion, not a statement\n'
                     '  "unknown"  - the origin could not be established')

    expression = entry.get('SPDX-License-Identifier', '')
    terms = license_terms(expression)
    known = doc.get('license', {})
    for term in terms:
        if term not in known:
            problems.add(where, f'`SPDX-License-Identifier` names {term!r}, '
                                'which has no [license.*] table',
                         f'Add a [license.{term}] table near the top of DATASETS.toml and\n'
                         f'add the full licence text at LICENSES/{term}.txt, or use one of\n'
                         'the licences already declared: ' + ', '.join(sorted(known)) + '.')

    needs_notes = provenance != 'verified' or UNKNOWN_LICENSE in terms
    if needs_notes and not entry.get('notes'):
        problems.add(where, '`notes` is required here but is missing',
                     'A dataset whose provenance is not "verified", or whose licence is\n'
                     f'{UNKNOWN_LICENSE}, must say in `notes` what was established, what\n'
                     'was not, and what a downstream user should do about it.')

    if provenance != 'unknown' and not entry.get('origin_url'):
        problems.add(where, '`origin_url` is missing',
                     'Record where the data came from. Only a dataset with\n'
                     '`provenance = "unknown"` may omit `origin_url`.')

    requires_credit = any(known.get(t, {}).get('attribution_required') for t in terms)
    if requires_credit and not entry.get('attribution'):
        problems.add(where, f'`{expression}` requires attribution but `attribution` is missing',
                     'Add the credit line the licence requires, for example:\n'
                     'attribution = "Grey Nurse Shark by rogerpeng1, licensed under CC BY-SA."')

    if entry.get('modified') and not entry.get('modification'):
        problems.add(where, '`modified = true` but `modification` is missing',
                     'Describe what was done to the file since it left its source, for\n'
                     'example: modification = "Decimated to 100k triangles and cast to float32."')

    collection = entry.get('collection')
    if collection is not None and collection not in doc.get('collection', {}):
        problems.add(where, f'`collection` is {collection!r}, which has no [collection.*] table',
                     f'Add a [collection."{collection}"] table, or use one of: '
                     + ', '.join(sorted(doc.get('collection', {}))) + '.')

    for reference in entry.get('references', []):
        if 'citation' not in reference:
            problems.add(where, 'a `references` entry has no `citation`',
                         'Every reference needs a `citation`; `doi` and `url` are optional.')


def check_coverage(doc: dict, files: list[str], problems: Problems) -> None:
    """Check that every file under Data/ belongs to exactly one dataset."""
    owners: dict[str, list[str]] = {path: [] for path in files}
    for entry in doc.get('dataset', []):
        name = entry.get('name', '?')
        for pattern in entry.get('path', []):
            if set(pattern) <= {'*', '?', '/'}:
                problems.add(
                    f'DATASETS.toml [[dataset]] name = {name!r}',
                    f'`path` pattern {pattern!r} claims every file under Data/',
                    'Name the files or the directory this dataset owns. A wildcard-only\n'
                    'pattern makes the coverage check meaningless.',
                )
            hits = [path for path in files if matches(pattern, path)]
            if not hits:
                problems.add(
                    f'DATASETS.toml [[dataset]] name = {name!r}',
                    f'`path` pattern {pattern!r} matches no tracked file under Data/',
                    'Correct the pattern, or remove it if the file was deleted. Patterns\n'
                    'are relative to Data/ and `dir/**` matches everything under `dir/`.',
                )
            for path in hits:
                owners[path].append(name)

    orphans = [path for path, own in owners.items() if not own and not is_forbidden(path)]
    groups: dict[str, list[str]] = {}
    for path in orphans:
        groups.setdefault(str(Path(path).parent), []).append(path)
    for parent, members in sorted(groups.items()):
        problems.add(
            'Data/' + (', Data/'.join(members) if len(members) < 4 else f'{parent}/ ({len(members)} files)'),
            'not covered by any [[dataset]] in DATASETS.toml',
            'Add a [[dataset]] block describing this data. A minimal block is:\n'
            '\n'
            '  [[dataset]]\n'
            f'  name = "{suggested_name(parent, members)}"\n'
            '  title = "Short human-readable name"\n'
            '  description = "One or two sentences about what the data is."\n'
            f'  path = {suggested_path(parent, members)}\n'
            '  SPDX-License-Identifier = "CC-BY-4.0"\n'
            '  provenance = "verified"\n'
            '  origin_url = "https://example.org/where-you-got-it"\n'
            '  attribution = "Credit line the licence requires."\n'
            '\n'
            'Keep the blocks sorted by `name`.',
        )

    for path, own in owners.items():
        if len(own) > 1:
            problems.add(
                f'Data/{path}',
                'this file is claimed by more than one dataset: ' + ', '.join(sorted(own)),
                'Narrow the `path` patterns so exactly one [[dataset]] owns each file.',
            )


def check_identical_files(doc: dict, files: list[str], problems: Problems) -> None:
    """Reject byte-identical files whose datasets disagree on licence or provenance."""
    blobs = subprocess.run(
        ['git', '-C', str(ROOT), 'ls-tree', '-r', 'HEAD', DATA_DIR],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    by_blob: dict[str, list[str]] = {}
    for line in blobs:
        if not line.strip():
            continue
        meta, path = line.split('\t', 1)
        rel = path[len(DATA_DIR) + 1:]
        if rel in files:
            by_blob.setdefault(meta.split()[2], []).append(rel)

    owners = {
        path: entry
        for entry in doc.get('dataset', [])
        for path in files
        if any(matches(pattern, path) for pattern in entry.get('path', []))
    }
    for paths in by_blob.values():
        if len(paths) < 2:
            continue
        for field, label, fix in (
            (
                'SPDX-License-Identifier',
                'different licences',
                'The same bytes have one origin. Decide which licence applies and give every copy that licence,\n'
                'recording the other route in `redistributed_from` and the\n'
                'duplication in `notes`.',
            ),
            (
                'provenance',
                'different provenance',
                'The same bytes have one origin, established once. Give every copy the\n'
                'provenance that reasoning supports, and put the reasoning where\n'
                'both can reach it rather than on one side only.',
            ),
        ):
            values = {owners[path].get(field) for path in paths if path in owners}
            if len(values) > 1:
                named = ', '.join(sorted(str(value) for value in values))
                problems.add(
                    ', '.join(f'Data/{path}' for path in sorted(paths)),
                    f'these files are byte-identical but carry {label}: {named}',
                    fix,
                )


def check_ordering_and_uniqueness(doc: dict, problems: Problems) -> None:
    """Check that dataset names are unique and blocks are sorted by name."""
    names = [entry.get('name') for entry in doc.get('dataset', []) if entry.get('name')]
    seen: set[str] = set()
    for name in names:
        if name in seen:
            problems.add(f'DATASETS.toml [[dataset]] name = {name!r}',
                         'this name is used by more than one dataset',
                         'Dataset names are the key downstream tools look up. Rename one.')
        seen.add(name)
    if names != sorted(names):
        first = next(
            (b for a, b in zip(names, names[1:]) if b < a), None
        )
        problems.add('DATASETS.toml', '[[dataset]] blocks are not sorted by `name`',
                     f'Move the block named {first!r} so the file stays alphabetical.'
                     if first else 'Sort the [[dataset]] blocks alphabetically by `name`.')


def check_unused_tables(doc: dict, problems: Problems) -> None:
    """Check that every declared licence and collection is actually referenced."""
    used_licenses: set[str] = set()
    used_collections: set[str] = set()
    for entry in doc.get('dataset', []):
        used_licenses.update(license_terms(entry.get('SPDX-License-Identifier', '')))
        if entry.get('collection'):
            used_collections.add(entry['collection'])
    for key in doc.get('license', {}):
        if key not in used_licenses:
            problems.add(f'DATASETS.toml [license.{key}]', 'no dataset uses this licence',
                         'Remove the table and its LICENSES/ text file, or point a dataset at it.')
    for key in doc.get('collection', {}):
        if key not in used_collections:
            problems.add(f'DATASETS.toml [collection."{key}"]', 'no dataset uses this collection',
                         'Remove the table, or point a dataset at it with `collection`.')


def check_orphan_license_texts(doc: dict, problems: Problems) -> None:
    """Check that LICENSES/ holds exactly the texts the licence tables name."""
    declared = {table.get('file') for table in doc.get('license', {}).values()}
    for path in sorted(LICENSES_DIR.glob('*.txt')):
        rel = str(path.relative_to(ROOT))
        if rel not in declared:
            problems.add(rel, 'this licence text is not named by any [license.*] table',
                         'Add the matching [license.*] table to DATASETS.toml, or delete the file.')


def main() -> int:
    """Validate DATASETS.toml and report every problem found."""
    problems = Problems()
    if not DATASETS_TOML.is_file():
        print(f'{DATASETS_TOML} is missing.')
        return 1
    try:
        doc = tomllib.loads(DATASETS_TOML.read_text(encoding='utf-8'))
    except tomllib.TOMLDecodeError as error:
        print(f'DATASETS.toml is not valid TOML: {error}')
        print(f'\nSee {DOCS} for the format reference.')
        return 1

    if doc.get('schema_version') != SCHEMA_VERSION:
        problems.add('DATASETS.toml', f'`schema_version` is {doc.get("schema_version")!r}',
                     f'This checker understands schema_version = {SCHEMA_VERSION}.')

    files = tracked_data_files()
    check_forbidden_files(files, problems)
    if not check_shape(doc, problems):
        return problems.report()
    check_license_tables(doc, problems)
    check_collection_tables(doc, problems)
    for index, entry in enumerate(doc.get('dataset', [])):
        check_dataset(entry, index, doc, problems)
    check_ordering_and_uniqueness(doc, problems)
    check_coverage(doc, files, problems)
    check_identical_files(doc, files, problems)
    check_unused_tables(doc, problems)
    check_orphan_license_texts(doc, problems)

    status = problems.report()
    if status == 0:
        print(f'{len(doc.get("dataset", []))} datasets cover {len(files)} files under Data/.')
    return status


if __name__ == '__main__':
    sys.exit(main())
