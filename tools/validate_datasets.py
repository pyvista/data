#!/usr/bin/env python3
"""Check that DATASETS.toml describes every file under Data/ and is well formed."""

from __future__ import annotations

import functools
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
SPDX_RE = re.compile(r'^[A-Za-z0-9.-]+\+?$')
URL_RE = re.compile(r'^https?://\S+$')
DOI_RE = re.compile(r'^10\.\d{4,9}/\S+$')
OPERATORS = ('AND', 'OR', 'WITH')
PROVENANCE = ('verified', 'inferred', 'unknown')
UNKNOWN_LICENSE = 'LicenseRef-Unknown'
PLACEHOLDER = 'FILL-ME-IN'

TOP_LEVEL_KEYS = ('schema_version', 'license', 'collection', 'dataset')
DATASET_REQUIRED = ('name', 'title', 'description', 'path', 'SPDX-License-Identifier', 'provenance')
DATASET_OPTIONAL = (
    'SPDX-FileCopyrightText', 'origin_url', 'origin_title', 'collection', 'authors',
    'attribution', 'redistributed_from', 'modified', 'modification', 'notes', 'references',
)
DATASET_STRINGS = (
    'name', 'title', 'description', 'SPDX-License-Identifier', 'provenance', 'origin_url',
    'origin_title', 'collection', 'attribution', 'modification', 'notes',
)
DATASET_STRING_LISTS = ('path', 'authors', 'SPDX-FileCopyrightText', 'redistributed_from')
DATASET_TABLE_LISTS = ('references',)
DATASET_BOOLEANS = ('modified',)
DATASET_URLS = ('origin_url',)
REFERENCE_KEYS = ('citation', 'doi', 'url')
LICENSE_REQUIRED = ('title', 'url', 'file', 'text_source', 'commercial_use',
                    'attribution_required', 'share_alike')
LICENSE_STRINGS = ('title', 'url', 'file', 'text_source')
LICENSE_BOOLEANS = ('commercial_use', 'attribution_required', 'share_alike')
COLLECTION_REQUIRED = ('title', 'url', 'description')

FORBIDDEN_STEMS = {
    'license', 'licence', 'licenses', 'licences', 'copying', 'copyright',
    'notice', 'notices', 'readme', 'readmes', 'citation', 'citations',
}
FORBIDDEN_SUFFIX = '.license'
DOCUMENT_SUFFIXES = (
    '', '.txt', '.md', '.markdown', '.rst', '.cff', '.bib', '.html', '.htm', '.adoc',
    '.pdf', '.rtf', '.tex', '.json', '.yaml', '.yml', '.xml', '.docx', '.odt',
)
STEM_RE = re.compile(r'^([a-z0-9]+)([.\-_]|$)')

PATTERN_FIX = (
    'Patterns are relative to Data/ with `/` as the separator: `dir/**` matches\n'
    'everything under `dir/`, `dir/*.vtk` the .vtk files directly in it.'
)


class Problems:
    """Collected validation failures, printed as an actionable report."""

    def __init__(self) -> None:
        """Start with no failures recorded."""
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


def index_blobs() -> dict[str, str]:
    """Map every tracked path under Data/, relative to Data/, to its blob id."""
    out = subprocess.run(
        ['git', '-C', str(ROOT), 'ls-files', '-s', '-z', DATA_DIR],
        capture_output=True, text=True, check=True,
    ).stdout.split('\0')
    blobs = {}
    for record in out:
        if not record:
            continue
        meta, path = record.split('\t', 1)
        if path.startswith(DATA_DIR + '/'):
            blobs[path[len(DATA_DIR) + 1:]] = meta.split()[1]
    return blobs


def tracked_data_files(blobs: dict[str, str]) -> list[str]:
    """List the tracked files a dataset must claim: every indexed path except dotfiles."""
    return sorted(path for path in blobs if not Path(path).name.startswith('.'))


@functools.lru_cache(maxsize=None)
def pattern_tokens(pattern: str) -> tuple[str, ...]:
    """Split a path pattern into `**/`, `**`, `*`, `?` and literal-character tokens."""
    tokens: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith('**/', index):
            tokens.append('**/')
            index += 3
        elif pattern.startswith('**', index):
            tokens.append('**')
            index += 2
        else:
            tokens.append(pattern[index])
            index += 1
    return tuple(tokens)


def _closure(states: set[int], tokens: tuple[str, ...]) -> set[int]:
    """Extend a set of pattern positions across the tokens that may match nothing."""
    pending = list(states)
    while pending:
        state = pending.pop()
        if state < len(tokens) and tokens[state] in ('*', '**', '**/') and state + 1 not in states:
            states.add(state + 1)
            pending.append(state + 1)
    return states


def matches(pattern: str, path: str) -> bool:
    """Match a path pattern against a path relative to Data/, in linear time."""
    tokens = pattern_tokens(pattern)
    end = len(tokens)
    inside = end + 1
    states = _closure({0}, tokens)
    for char in path:
        advanced: set[int] = set()
        for state in states:
            if state >= inside:
                advanced.add(state)
                if char == '/':
                    advanced.add(state - inside + 1)
                continue
            if state == end:
                continue
            token = tokens[state]
            if token == '**':
                advanced.add(state)
            elif token == '**/':
                advanced.add(state + inside)
                if char == '/':
                    advanced.add(state + 1)
            elif token == '*':
                if char != '/':
                    advanced.add(state)
            elif token == '?':
                if char != '/':
                    advanced.add(state + 1)
            elif token == char:
                advanced.add(state + 1)
        if not advanced:
            return False
        states = _closure(advanced, tokens)
    return end in states


def check_pattern(pattern: str) -> str | None:
    """Return why a path pattern is unusable, or None when it is well formed."""
    if not pattern.strip():
        return 'is empty'
    if '\\' in pattern:
        return 'contains a backslash; the separator is `/`'
    if pattern.startswith('/') or pattern.endswith('/') or '//' in pattern:
        return 'is not a relative path: no leading, trailing or doubled `/`'
    if not pattern.strip('*?/'):
        return 'claims every file under Data/'
    return None


def license_terms(expression: str) -> list[str]:
    """Split an SPDX expression into the licence ids it names, raising ValueError when malformed."""
    tokens = re.findall(r'\(|\)|[^\s()]+', expression)
    terms: list[str] = []
    depth = 0
    expect_operand = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        upper = token.upper()
        if token == '(':
            if not expect_operand:
                raise ValueError('an operator must precede `(`')
            depth += 1
        elif token == ')':
            if expect_operand or depth == 0:
                raise ValueError('unbalanced `)`')
            depth -= 1
        elif upper in ('AND', 'OR'):
            if expect_operand:
                raise ValueError(f'`{token}` has no licence before it')
            expect_operand = True
        elif upper == 'WITH':
            if expect_operand or index + 1 >= len(tokens) or not SPDX_RE.match(tokens[index + 1]):
                raise ValueError('`WITH` must join a licence and an exception')
            index += 1
        elif expect_operand:
            if not SPDX_RE.match(token):
                raise ValueError(f'{token!r} is not a licence identifier')
            terms.append(token)
            expect_operand = False
        else:
            raise ValueError(f'{token!r} follows a licence without AND or OR')
        index += 1
    if expect_operand:
        raise ValueError('the expression ends without a licence')
    if depth:
        raise ValueError('unbalanced `(`')
    return terms


def known_terms(expression: object) -> list[str]:
    """Return the licence ids an expression names, or none when it cannot be parsed."""
    if not isinstance(expression, str):
        return []
    try:
        return license_terms(expression)
    except ValueError:
        return []


def is_forbidden(path: str) -> bool:
    """Say whether a path is a per-dataset metadata file that DATASETS.toml replaces."""
    name = Path(path).name.casefold()
    if name.endswith(FORBIDDEN_SUFFIX):
        return True
    match = STEM_RE.match(name)
    if not match or match.group(1) not in FORBIDDEN_STEMS:
        return False
    if match.group(2) in ('', '.'):
        return True
    return Path(name).suffix in DOCUMENT_SUFFIXES


def slugify(text: str) -> str:
    """Turn a file or directory name into a candidate dataset name."""
    return re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_') or 'new_dataset'


def suggested_name(parent: str, members: list[str]) -> str:
    """Suggest a dataset name for a group of uncovered files."""
    return slugify(parent if parent != '.' else Path(members[0]).stem)


def suggested_path(parent: str, members: list[str], claimed_dirs: set[str]) -> str:
    """Suggest a `path` value for a group of uncovered files."""
    shared = parent in claimed_dirs or any(other.startswith(parent + '/') for other in claimed_dirs)
    if parent != '.' and len(members) > 1 and not shared:
        return f'["{parent}/**"]'
    return '[' + ', '.join(f'"{member}"' for member in members) + ']'


def check_forbidden_files(paths: list[str], problems: Problems) -> None:
    """Reject per-dataset licence, readme and citation files under Data/."""
    for path in paths:
        if is_forbidden(path):
            problems.add(
                f'Data/{path}',
                'per-dataset metadata files are not allowed under Data/',
                'Delete this file and put its content in the dataset\'s [[dataset]] block\n'
                'in DATASETS.toml instead: the source in `origin_url`, the licence in\n'
                '`SPDX-License-Identifier`, the required credit in `attribution`, any\n'
                'processing in `modification`, the citation in `references`, and\n'
                'everything else in `notes`.',
            )


def _type_name(value: object) -> str:
    """Name a TOML value's type the way a contributor would write it."""
    return {bool: 'boolean', int: 'integer', float: 'float', str: 'string',
            list: 'array', dict: 'table'}.get(type(value), type(value).__name__)


def _dataset_where(entry: dict, index: int) -> str:
    """Name a dataset block in the report, by name when it has one."""
    name = entry.get('name')
    if isinstance(name, str) and name:
        return f'DATASETS.toml [[dataset]] name = {name!r}'
    return f'DATASETS.toml [[dataset]] #{index + 1}'


def _check_string_list(where: str, field: str, value: object, problems: Problems) -> bool:
    """Report a field that is not an array of strings, returning whether it is one."""
    if not isinstance(value, list):
        example = value if isinstance(value, str) else 'one-value'
        problems.add(where, f'`{field}` is a {_type_name(value)}, not an array',
                     f'Write `{field}` as an array, even with one element:\n'
                     f'  {field} = ["{example}"]')
        return False
    for element in value:
        if not isinstance(element, str):
            problems.add(where, f'`{field}` holds a {_type_name(element)}, not a string',
                         f'Every entry of `{field}` must be a string:\n'
                         f'  {field} = ["one-value", "another"]')
            return False
    return True


def _check_entry_shape(entry: dict, index: int, problems: Problems) -> None:
    """Type-check every field of one dataset block."""
    where = _dataset_where(entry, index)
    for field in DATASET_STRINGS:
        value = entry.get(field)
        if value is not None and not isinstance(value, str):
            problems.add(where, f'`{field}` is a {_type_name(value)}, not a string',
                         f'Write `{field}` as a quoted string:\n  {field} = "one-value"')
    for field in DATASET_BOOLEANS:
        value = entry.get(field)
        if value is not None and not isinstance(value, bool):
            problems.add(where, f'`{field}` is a {_type_name(value)}, not a boolean',
                         f'Write `{field}` as `true` or `false`, unquoted.')
    for field in DATASET_STRING_LISTS:
        value = entry.get(field)
        if value is not None:
            _check_string_list(where, field, value, problems)
    for field in DATASET_TABLE_LISTS:
        value = entry.get(field)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            problems.add(where, f'`{field}` is not an array of tables',
                         f'Write `{field}` as an array of tables:\n'
                         '  references = [{ citation = "...", doi = "..." }]')
            continue
        for reference in value:
            for key, item in reference.items():
                if key in REFERENCE_KEYS and not isinstance(item, str):
                    problems.add(where, f'a `references` entry has `{key}` as a {_type_name(item)}, not a string',
                                 f'Write `{key}` as a quoted string.')


def check_shape(doc: dict, problems: Problems) -> bool:
    """Check the document's structure and types, and say whether the deeper checks can run."""
    ok = True
    for key, kind, shape in (
        ('license', dict, '[license."SPDX-Id"] tables'),
        ('collection', dict, '[collection."name"] tables'),
        ('dataset', list, '[[dataset]] blocks'),
    ):
        value = doc.get(key)
        if value is not None and not isinstance(value, kind):
            problems.add(f'DATASETS.toml `{key}`', f'this is a {_type_name(value)}, not {shape}',
                         f'`{key}` is written as {shape}, not as a bare key. For example:\n'
                         '  [license."CC-BY-4.0"]\n'
                         '  title = "Creative Commons Attribution 4.0 International"')
            ok = False
    for index, entry in enumerate(doc.get('dataset') if isinstance(doc.get('dataset'), list) else []):
        if not isinstance(entry, dict):
            problems.add(f'DATASETS.toml [[dataset]] #{index + 1}',
                         f'this is a {_type_name(entry)}, not a table',
                         'Each dataset is a `[[dataset]]` table with `name`, `title` and the rest.')
            ok = False
            continue
        _check_entry_shape(entry, index, problems)
    for kind, strings, booleans in (
        ('license', LICENSE_STRINGS, LICENSE_BOOLEANS),
        ('collection', COLLECTION_REQUIRED, ()),
    ):
        tables = doc.get(kind)
        for key, table in (tables if isinstance(tables, dict) else {}).items():
            where = f'DATASETS.toml [{kind}."{key}"]'
            if not isinstance(table, dict):
                problems.add(where, f'this is a {_type_name(table)}, not a table',
                             f'Write it as a table:\n  [{kind}."{key}"]\n  title = "..."')
                ok = False
                continue
            for field in strings:
                value = table.get(field)
                if value is not None and not isinstance(value, str):
                    problems.add(where, f'`{field}` is a {_type_name(value)}, not a string',
                                 f'Write `{field}` as a quoted string.')
            for field in booleans:
                value = table.get(field)
                if value is not None and not isinstance(value, bool):
                    problems.add(where, f'`{field}` is a {_type_name(value)}, not a boolean',
                                 f'Write `{field}` as `true` or `false`, unquoted.')
    return ok


def check_top_level(doc: dict, problems: Problems) -> None:
    """Check `schema_version` and reject keys the format does not define."""
    version = doc.get('schema_version')
    if type(version) is not int or version != SCHEMA_VERSION:
        problems.add('DATASETS.toml', f'`schema_version` is {version!r}',
                     f'This checker understands `schema_version = {SCHEMA_VERSION}`, an integer.')
    unknown = set(doc) - set(TOP_LEVEL_KEYS)
    if unknown:
        problems.add('DATASETS.toml', f'unknown top-level key(s): {", ".join(sorted(unknown))}',
                     'The file holds `schema_version`, `[license.*]` and `[collection.*]`\n'
                     'tables and `[[dataset]]` blocks, nothing else.')


def _datasets(doc: dict) -> list[dict]:
    """Return the well-formed `[[dataset]]` blocks of a document."""
    datasets = doc.get('dataset')
    if not isinstance(datasets, list):
        return []
    return [entry for entry in datasets if isinstance(entry, dict)]


def _tables(doc: dict, kind: str) -> dict[str, dict]:
    """Return the well-formed `[kind.*]` tables of a document."""
    tables = doc.get(kind)
    if not isinstance(tables, dict):
        return {}
    return {key: table for key, table in tables.items() if isinstance(table, dict)}


def check_license_tables(doc: dict, problems: Problems) -> None:
    """Check every [license.*] table and the licence text it points at."""
    for key, table in _tables(doc, 'license').items():
        where = f'DATASETS.toml [license."{key}"]'
        if not SPDX_RE.match(key):
            problems.add(where, f'{key!r} is not a valid licence identifier',
                         'Use an SPDX identifier such as `CC-BY-4.0`, or a custom\n'
                         '`LicenseRef-Something` identifier for terms SPDX does not list.')
        for field in LICENSE_REQUIRED:
            if field not in table:
                problems.add(where, f'missing required key `{field}`',
                             f'Add `{field}` to the [license."{key}"] table. See '
                             'an existing licence table for the shape.')
        unknown = set(table) - set(LICENSE_REQUIRED)
        if unknown:
            problems.add(where, f'unknown key(s): {", ".join(sorted(unknown))}',
                         'Remove the key or correct the spelling. A licence table has exactly:\n'
                         + ', '.join(f'`{f}`' for f in LICENSE_REQUIRED) + '.')
        for field in LICENSE_STRINGS:
            value = table.get(field)
            if isinstance(value, str) and not value.strip():
                problems.add(where, f'`{field}` is empty',
                             'Say where the text in `file` came from: the URL you copied it\n'
                             'from, or a sentence saying it was written for this repository.'
                             if field == 'text_source' else f'Give `{field}` a value.')
        url = table.get('url')
        if isinstance(url, str) and url.strip() and not URL_RE.match(url):
            problems.add(where, f'`url` is {url!r}, which is not an http(s) URL',
                         'Record the licence page as a full URL, starting with https:// or http://.')
        path = table.get('file')
        if isinstance(path, str) and path.strip():
            if path != f'LICENSES/{key}.txt':
                problems.add(where, f'`file` is {path!r}, not "LICENSES/{key}.txt"',
                             'Licence texts live in LICENSES/ and are named by their identifier:\n'
                             f'  file = "LICENSES/{key}.txt"')
            elif not (ROOT / path).is_file():
                problems.add(where, f'`file` points at {path}, which does not exist',
                             f'Add the full licence text at {path}. For an SPDX licence,\n'
                             'copy it from https://github.com/spdx/license-list-data/tree/main/text.')


def check_collection_tables(doc: dict, problems: Problems) -> None:
    """Check every [collection.*] table."""
    for key, table in _tables(doc, 'collection').items():
        where = f'DATASETS.toml [collection."{key}"]'
        for field in COLLECTION_REQUIRED:
            if field not in table:
                problems.add(where, f'missing required key `{field}`',
                             f'Add `{field}` to the [collection."{key}"] table.')
        unknown = set(table) - set(COLLECTION_REQUIRED)
        if unknown:
            problems.add(where, f'unknown key(s): {", ".join(sorted(unknown))}',
                         'Remove the key or correct the spelling. A collection table has exactly:\n'
                         + ', '.join(f'`{f}`' for f in COLLECTION_REQUIRED) + '.')
        for field in COLLECTION_REQUIRED:
            value = table.get(field)
            if isinstance(value, str) and not value.strip():
                problems.add(where, f'`{field}` is empty', f'Give `{field}` a value.')
        url = table.get('url')
        if isinstance(url, str) and url.strip() and not URL_RE.match(url):
            problems.add(where, f'`url` is {url!r}, which is not an http(s) URL',
                         'Record the collection page as a full URL, starting with https:// or http://.')


def field_missing(value: object) -> bool:
    """Whether a required string is absent or only whitespace."""
    return not isinstance(value, str) or not value.strip()


def _check_expression(entry: dict, where: str, doc: dict, problems: Problems) -> list[str]:
    """Check the licence expression of a block and return the identifiers it resolves."""
    expression = entry.get('SPDX-License-Identifier')
    if not isinstance(expression, str) or not expression.strip():
        return []
    try:
        terms = license_terms(expression)
    except ValueError as error:
        problems.add(where, f'`SPDX-License-Identifier` {expression!r} is not a well-formed expression: {error}',
                     'Write one identifier, or identifiers joined by AND or OR, for example\n'
                     '`CC-BY-4.0`, `MIT OR Apache-2.0`, `LicenseRef-Unknown`.')
        return []
    known = _tables(doc, 'license')
    folded = {key.casefold(): key for key in known}
    for term in terms:
        if term in known:
            continue
        if term.casefold() in folded:
            problems.add(where, f'`SPDX-License-Identifier` names {term!r}, '
                                f'which has no [license.*] table; {folded[term.casefold()]!r} does',
                         f'Identifiers are case-sensitive. Write `{folded[term.casefold()]}`.')
        else:
            problems.add(where, f'`SPDX-License-Identifier` names {term!r}, '
                                'which has no [license.*] table',
                         f'Add a [license."{term}"] table near the top of DATASETS.toml and\n'
                         f'add the full licence text at LICENSES/{term}.txt, or use one of\n'
                         'the licences already declared: ' + ', '.join(sorted(known)) + '.')
    return terms


def check_dataset(entry: dict, index: int, doc: dict, problems: Problems) -> None:
    """Check one [[dataset]] block against the schema."""
    where = _dataset_where(entry, index)
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
    if entry and next(iter(entry)) != 'name':
        problems.add(where, '`name` is not the first key of the block',
                     'Put `name = "..."` on the line after `[[dataset]]`, before every other key.')

    for field in DATASET_STRINGS:
        value = entry.get(field)
        if isinstance(value, str) and not value.strip():
            problems.add(where, f'`{field}` is empty',
                         'Name the licence, or `LicenseRef-Unknown` when the terms could not\n'
                         'be established. An empty value skips every licence check.'
                         if field == 'SPDX-License-Identifier'
                         else f'Give `{field}` a value, or remove the key.')
    for field in DATASET_STRING_LISTS:
        value = entry.get(field)
        if isinstance(value, list) and any(isinstance(item, str) and not item.strip() for item in value):
            problems.add(where, f'`{field}` holds an empty string',
                         f'Remove the empty entry from `{field}`.')

    name = entry.get('name')
    if isinstance(name, str) and name.strip() and not NAME_RE.match(name):
        problems.add(where, f'`name` {name!r} is not a valid identifier',
                     'Use lowercase letters, digits and underscores, starting with a\n'
                     'letter or digit, for example `grey_nurse_shark`.')

    if entry.get('path') == []:
        problems.add(where, '`path` is empty, so this dataset claims no file',
                     'List the files or the directory this dataset owns, for example:\n'
                     '  path = ["my_dataset/**"]')

    provenance = entry.get('provenance')
    if isinstance(provenance, str) and provenance.strip() and provenance not in PROVENANCE:
        problems.add(where, f'`provenance` is {provenance!r}',
                     'Set `provenance` to one of: '
                     + ', '.join(f'"{p}"' for p in PROVENANCE) + '.\n'
                     '  "verified" - the source states the origin, or the bytes prove it\n'
                     '  "inferred" - the origin is a reasoned conclusion, not a statement\n'
                     '  "unknown"  - the origin could not be established')

    terms = _check_expression(entry, where, doc, problems)
    known = _tables(doc, 'license')
    flags = [known.get(term, {}) for term in terms]

    for field in DATASET_URLS:
        value = entry.get(field)
        if isinstance(value, str) and value.strip() and not URL_RE.match(value):
            problems.add(where, f'`{field}` is {value!r}, which is not an http(s) URL',
                         'Record the page as a full URL, starting with https:// or http://.')
    routes = entry.get('redistributed_from')
    if isinstance(routes, list):
        for value in routes:
            if isinstance(value, str) and value.strip() and not URL_RE.match(value):
                problems.add(where, f'`redistributed_from` holds {value!r}, which is not an http(s) URL',
                             'Record each route as a full URL, starting with https:// or http://.')

    share_alike = any(table.get('share_alike') is True for table in flags)
    needs_notes = provenance != 'verified' or UNKNOWN_LICENSE in terms or share_alike
    if needs_notes and 'notes' not in entry:
        problems.add(where, '`notes` is required here but is missing',
                     'A dataset whose provenance is not "verified", whose licence is\n'
                     f'{UNKNOWN_LICENSE} or whose licence is share-alike must say in `notes`\n'
                     'what was established, what was not, and what a downstream user\n'
                     'should do about it.')

    if provenance == 'unknown':
        if 'origin_url' in entry:
            problems.add(where, '`provenance = "unknown"` but `origin_url` is set',
                         'An origin that can be named is not unknown. Remove `origin_url`, or\n'
                         'set `provenance = "inferred"` and say in `notes` what the page establishes.')
        if terms and terms != [UNKNOWN_LICENSE]:
            problems.add(where, f'`provenance = "unknown"` but the licence is {entry["SPDX-License-Identifier"]!r}',
                         'Terms cannot be established for data whose origin is unknown. Set\n'
                         f'`SPDX-License-Identifier = "{UNKNOWN_LICENSE}"`, or establish the origin\n'
                         'and record it with `provenance = "inferred"` or `"verified"`.')
    elif 'origin_url' not in entry:
        problems.add(where, '`origin_url` is missing',
                     'Record where the data came from. Only a dataset with\n'
                     '`provenance = "unknown"` may omit `origin_url`.')

    requires_credit = any(table.get('attribution_required') is True for table in flags)
    if requires_credit and 'attribution' not in entry:
        problems.add(where, f'`{entry["SPDX-License-Identifier"]}` requires attribution but `attribution` is missing',
                     'Add the credit line the licence requires, for example:\n'
                     'attribution = "Grey Nurse Shark by rogerpeng1, licensed under CC BY-SA."')

    modified = entry.get('modified')
    if modified is True and 'modification' not in entry:
        problems.add(where, '`modified = true` but `modification` is missing',
                     'Describe what was done to the file since it left its source, for\n'
                     'example: modification = "Decimated to 100k triangles and cast to float32."')
    if 'modification' in entry and modified is not True:
        problems.add(where, '`modification` is set but `modified` is not `true`',
                     'Set `modified = true` when the file differs from what the source\n'
                     'published, or remove `modification`.')

    collection = entry.get('collection')
    collections = _tables(doc, 'collection')
    if isinstance(collection, str) and collection.strip() and collection not in collections:
        problems.add(where, f'`collection` is {collection!r}, which has no [collection.*] table',
                     f'Add a [collection."{collection}"] table, or use one of: '
                     + ', '.join(sorted(collections)) + '.')

    references = entry.get('references')
    for reference in references if isinstance(references, list) else []:
        if not isinstance(reference, dict):
            continue
        if 'citation' not in reference:
            problems.add(where, 'a `references` entry has no `citation`',
                         'Every reference needs a `citation`; `doi` and `url` are optional.')
        elif field_missing(reference.get('citation')):
            if isinstance(reference.get('citation'), str):
                problems.add(where, 'a `references` entry has an empty `citation`',
                             'Give `citation` the reference text.')
        extra = set(reference) - set(REFERENCE_KEYS)
        if extra:
            problems.add(where, f'a `references` entry has unknown key(s): {", ".join(sorted(extra))}',
                         'A reference holds `citation`, `doi` and `url` only.')
        doi = reference.get('doi')
        if isinstance(doi, str) and not DOI_RE.match(doi):
            problems.add(where, f'a `references` entry has `doi` {doi!r}, which is not a bare DOI',
                         'Write the identifier alone, for example `10.1145/237170.237270`,\n'
                         'not a doi.org URL.')
        url = reference.get('url')
        if isinstance(url, str) and not URL_RE.match(url):
            problems.add(where, f'a `references` entry has `url` {url!r}, which is not an http(s) URL',
                         'Record the page as a full URL, starting with https:// or http://.')


def check_coverage(doc: dict, files: list[str], problems: Problems) -> dict[str, list[str]]:
    """Check that every file under Data/ belongs to exactly one dataset, returning the owners."""
    owners: dict[str, list[str]] = {path: [] for path in files}
    for index, entry in enumerate(_datasets(doc)):
        where = _dataset_where(entry, index)
        name = entry.get('name') if isinstance(entry.get('name'), str) else f'#{index + 1}'
        patterns = entry.get('path')
        if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
            continue
        for pattern in sorted({p for p in patterns if patterns.count(p) > 1}):
            problems.add(where, f'`path` lists {pattern!r} more than once', 'Remove the duplicate.')
        claimed: set[str] = set()
        for pattern in dict.fromkeys(patterns):
            fault = check_pattern(pattern)
            if fault:
                problems.add(where, f'`path` pattern {pattern!r} {fault}',
                             'Name the files or the directory this dataset owns.\n' + PATTERN_FIX)
                continue
            hits = [path for path in files if matches(pattern, path)]
            if not hits:
                problems.add(where, f'`path` pattern {pattern!r} matches no tracked file under Data/',
                             'Correct the pattern, or remove it if the file was deleted.\n' + PATTERN_FIX)
            overlap = claimed.intersection(hits)
            if overlap:
                problems.add(where,
                             f'`path` pattern {pattern!r} overlaps an earlier pattern of this block '
                             f'on {len(overlap)} file(s), for example Data/{min(overlap)}',
                             'Each file should match one pattern of the block. Drop the pattern\n'
                             'the other already covers, or narrow one of them.')
            claimed.update(hits)
        for path in claimed:
            owners[path].append(name)

    claimed_dirs = {str(Path(path).parent) for path, own in owners.items() if own}
    orphans = [path for path, own in owners.items() if not own and not is_forbidden(path)]
    groups: dict[str, list[str]] = {}
    for path in orphans:
        groups.setdefault(str(Path(path).parent), []).append(path)
    for parent, members in sorted(groups.items()):
        shown = ', '.join(f'Data/{member}' for member in members[:10])
        if len(members) > 10:
            shown += f' and {len(members) - 10} more file(s) in ' + ('Data/' if parent == '.' else f'Data/{parent}/')
        problems.add(
            shown,
            'not covered by any [[dataset]] in DATASETS.toml',
            'Add a [[dataset]] block describing this data, replacing every placeholder\n'
            '(the validator rejects the block as written here):\n'
            '\n'
            '  [[dataset]]\n'
            f'  name = "{suggested_name(parent, members)}"\n'
            '  title = "Short human-readable name"\n'
            '  description = "One or two sentences about what the data is."\n'
            f'  path = {suggested_path(parent, members, claimed_dirs)}\n'
            f'  SPDX-License-Identifier = "{PLACEHOLDER}"\n'
            f'  provenance = "{PLACEHOLDER}"\n'
            f'  origin_url = "{PLACEHOLDER}"\n'
            '  attribution = "Credit line, when the licence requires one."\n'
            '\n'
            'Read the licence and the origin off the source page. Keep the blocks\n'
            'sorted by `name`.',
        )

    for path, own in owners.items():
        if len(own) > 1:
            problems.add(
                f'Data/{path}',
                'this file is claimed by more than one dataset: ' + ', '.join(sorted(own)),
                'Narrow the `path` patterns so exactly one [[dataset]] owns each file.',
            )
    return owners


def check_identical_files(doc: dict, blobs: dict[str, str], owners: dict[str, list[str]],
                          problems: Problems) -> None:
    """Reject byte-identical files whose datasets disagree on licence or provenance."""
    by_blob: dict[str, list[str]] = {}
    for path, blob in blobs.items():
        if path in owners:
            by_blob.setdefault(blob, []).append(path)
    entries = {entry.get('name'): entry for entry in _datasets(doc)}
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
            values = {
                entries[name].get(field)
                for path in paths
                for name in owners.get(path, [])
                if name in entries
            }
            if len(values) > 1:
                named = ', '.join(sorted(str(value) for value in values))
                problems.add(
                    ', '.join(f'Data/{path}' for path in sorted(paths)),
                    f'these files are byte-identical but carry {label}: {named}',
                    fix,
                )


def check_ordering_and_uniqueness(doc: dict, problems: Problems) -> None:
    """Check that dataset names are unique and blocks are sorted by name."""
    names = [entry.get('name') for entry in _datasets(doc) if isinstance(entry.get('name'), str)]
    seen: set[str] = set()
    for name in names:
        if name in seen:
            problems.add(f'DATASETS.toml [[dataset]] name = {name!r}',
                         'this name is used by more than one dataset',
                         'Dataset names are the key downstream tools look up. Rename one.')
        seen.add(name)
    if names != sorted(names):
        before, after = next((a, b) for a, b in zip(names, names[1:]) if b < a)
        problems.add('DATASETS.toml', '[[dataset]] blocks are not sorted by `name`',
                     f'{after!r} follows {before!r} but sorts before it. Move one of the two so\n'
                     'the file stays in plain codepoint order (digits, then `_`, then letters).')


def check_unused_tables(doc: dict, problems: Problems) -> None:
    """Check that every declared licence and collection is actually referenced."""
    used_licenses: set[str] = set()
    used_collections: set[str] = set()
    for entry in _datasets(doc):
        used_licenses.update(known_terms(entry.get('SPDX-License-Identifier')))
        if isinstance(entry.get('collection'), str):
            used_collections.add(entry['collection'])
    for key in _tables(doc, 'license'):
        if key not in used_licenses:
            problems.add(f'DATASETS.toml [license."{key}"]', 'no dataset uses this licence',
                         'Remove the table and its LICENSES/ text file, or point a dataset at it.')
    for key in _tables(doc, 'collection'):
        if key not in used_collections:
            problems.add(f'DATASETS.toml [collection."{key}"]', 'no dataset uses this collection',
                         'Remove the table, or point a dataset at it with `collection`.')


def check_orphan_license_texts(doc: dict, problems: Problems) -> None:
    """Check that LICENSES/ holds exactly the texts the licence tables name."""
    declared = {table.get('file') for table in _tables(doc, 'license').values()}
    for path in sorted(LICENSES_DIR.iterdir()) if LICENSES_DIR.is_dir() else []:
        if path.name.startswith('.'):
            continue
        rel = str(path.relative_to(ROOT))
        if rel not in declared:
            problems.add(rel, 'this file in LICENSES/ is not named by any [license.*] table',
                         'Add the matching [license.*] table to DATASETS.toml, or delete the file.')


def check_all(doc: dict, blobs: dict[str, str], problems: Problems) -> None:
    """Run every check on a parsed document, given the tracked paths under Data/."""
    check_top_level(doc, problems)
    check_forbidden_files(sorted(blobs), problems)
    if not check_shape(doc, problems):
        return
    files = tracked_data_files(blobs)
    check_license_tables(doc, problems)
    check_collection_tables(doc, problems)
    for index, entry in enumerate(_datasets(doc)):
        check_dataset(entry, index, doc, problems)
    check_ordering_and_uniqueness(doc, problems)
    owners = check_coverage(doc, files, problems)
    check_identical_files(doc, blobs, owners, problems)
    check_unused_tables(doc, problems)
    check_orphan_license_texts(doc, problems)


def main() -> int:
    """Validate DATASETS.toml and report every problem found."""
    problems = Problems()
    if not DATASETS_TOML.is_file():
        print(f'{DATASETS_TOML} is missing.')
        return 1
    try:
        doc = tomllib.loads(DATASETS_TOML.read_text(encoding='utf-8-sig'))
    except UnicodeDecodeError as error:
        print(f'DATASETS.toml is not UTF-8: byte {error.start} {error.reason}. Save the file as UTF-8.')
        return 1
    except tomllib.TOMLDecodeError as error:
        print(f'DATASETS.toml is not valid TOML: {error}')
        print(f'\nSee {DOCS} for the format reference.')
        return 1
    try:
        blobs = index_blobs()
    except (OSError, subprocess.CalledProcessError) as error:
        detail = (getattr(error, 'stderr', None) or str(error)).strip()
        print(f'Could not list the files git tracks under {DATA_DIR}/: {detail}')
        print('Run the validator inside a git checkout of pyvista/data, with git on PATH.')
        return 1

    check_all(doc, blobs, problems)
    status = problems.report()
    if status == 0:
        print(f'{len(_datasets(doc))} datasets cover {len(tracked_data_files(blobs))} files under Data/.')
    return status


if __name__ == '__main__':
    sys.exit(main())
