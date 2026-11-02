"""Tests for the dataset table validator, run with `python -m pytest tools/`."""

from __future__ import annotations

import random
import re
import subprocess
import time
import tomllib
from pathlib import Path

import pytest

import validate_datasets as v
from validate_datasets import DATASETS_TOML
from validate_datasets import ROOT
from validate_datasets import Problems
from validate_datasets import check_all
from validate_datasets import check_collection_tables
from validate_datasets import check_coverage
from validate_datasets import check_dataset
from validate_datasets import check_identical_files
from validate_datasets import check_license_tables
from validate_datasets import check_ordering_and_uniqueness
from validate_datasets import check_orphan_license_texts
from validate_datasets import check_pattern
from validate_datasets import check_shape
from validate_datasets import check_top_level
from validate_datasets import check_unused_tables
from validate_datasets import field_missing
from validate_datasets import index_blobs
from validate_datasets import is_forbidden
from validate_datasets import known_terms
from validate_datasets import license_terms
from validate_datasets import matches
from validate_datasets import pattern_tokens
from validate_datasets import slugify
from validate_datasets import suggested_name
from validate_datasets import suggested_path
from validate_datasets import tracked_data_files

PUBLISHED = tomllib.loads(DATASETS_TOML.read_text(encoding='utf-8'))


def whats(problems: Problems) -> list[str]:
    """Return the problem sentences a run recorded."""
    return [what for _, what, _ in problems.items]


# ---------------------------------------------------------------------------
# Path patterns


@pytest.mark.parametrize(
    ('pattern', 'path', 'expected'),
    [
        ('a.vtk', 'a.vtk', True),
        ('a.vtk', 'axvtk', False),  # the dot is literal
        ('*', 'a.vtk', True),
        ('*', 'dir/a.vtk', False),  # `*` stops at a separator
        ('dir/*', 'dir/a.vtk', True),
        ('dir/*', 'dir/sub/a.vtk', False),
        ('dir/**', 'dir/a.vtk', True),
        ('dir/**', 'dir/sub/a.vtk', True),  # `**` crosses one
        ('dir/**', 'dir', False),
        ('dir/**', 'directory/a.vtk', False),  # the separator is required
        ('sim_?.vtu', 'sim_1.vtu', True),
        ('sim_?.vtu', 'sim_12.vtu', False),
        ('sim_?.vtu', 'sim_/.vtu', False),
        ('a[bc].vtk', 'a[bc].vtk', True),  # brackets are literal, not a class
        ('a[bc].vtk', 'ab.vtk', False),
        ('dir/**/x.vtk', 'dir/x.vtk', True),  # an interior `**` also matches zero directories
        ('dir/**/x.vtk', 'dir/a/x.vtk', True),
        ('dir/**/x.vtk', 'dir/a/b/x.vtk', True),
        ('dir/**/*.vtk', 'dir/x.vtk', True),
        ('dir/**/*.vtk', 'dir/a/x.vtk', True),
        ('dir/**/*.vtk', 'dir/a/x.txt', False),
        ('**/x.vtk', 'x.vtk', True),
        ('**/x.vtk', 'a/b/x.vtk', True),
        ('dir/*/**', 'dir/a/x.vtk', True),  # a wildcard before `/**` is honoured
        ('dir/*/**', 'dir/x.vtk', False),
        ('sim_?/**', 'sim_1/a.vtu', True),
        ('**', 'a/b/c', True),
        ('*.vtk', 'a.vtk', True),
        ('*.vtk', 'a.vtk.bak', False),
        ('', 'a.vtk', False),
        ('', '', True),
    ],
)
def test_matches(pattern, path, expected):
    """The documented pattern rules, plus the gitignore zero-directory rule for `**`."""
    assert matches(pattern, path) is expected


@pytest.mark.parametrize(
    ('pattern', 'path'),
    [
        ('*a' * 14 + '*b', 'a' * 39 + 'c'),
        ('*a' * 30 + '*b', 'a' * 300),
        ('**/' * 8 + '*.vtk', 'x/' * 60 + 'y.txt'),
        ('*' * 30 + '.vtk', 'a' * 25 + '.txt'),
        ('*?' * 30, 'Victorian_Goblet_face_illusion/Vase.stl'),
        ('a*a*a*a*a*a*a*a*a*a*b', 'a' * 100),
    ],
)
def test_matches_never_backtracks(pattern, path):
    """Patterns that hang a regex matcher answer in well under a millisecond each."""
    started = time.perf_counter()
    assert matches(pattern, path) is False
    assert time.perf_counter() - started < 0.05


def _reference_regex(pattern: str) -> re.Pattern[str]:
    """Translate a pattern to a regex, the slow way, for cross-checking on short inputs."""
    out, index = [], 0
    while index < len(pattern):
        if pattern.startswith('**/', index):
            out.append('(?:.*/)?')
            index += 3
        elif pattern.startswith('**', index):
            out.append('.*')
            index += 2
        elif pattern[index] == '*':
            out.append('[^/]*')
            index += 1
        elif pattern[index] == '?':
            out.append('[^/]')
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile('^' + ''.join(out) + '$')


def test_matches_agrees_with_a_regex_on_short_inputs():
    """The linear matcher and a regex with the same grammar agree on random short cases."""
    generator = random.Random(1234)
    alphabet = 'ab/.'
    for _ in range(5000):
        pattern = ''.join(generator.choice(alphabet + '**??') for _ in range(generator.randint(0, 7)))
        path = ''.join(generator.choice(alphabet) for _ in range(generator.randint(0, 9)))
        assert matches(pattern, path) is bool(_reference_regex(pattern).match(path)), (pattern, path)


def test_pattern_tokens():
    """`**/`, `**`, `*` and `?` are tokens; everything else is one literal character."""
    assert pattern_tokens('a/**/b*.?') == ('a', '/', '**/', 'b', '*', '.', '?')
    assert pattern_tokens('dir/**') == ('d', 'i', 'r', '/', '**')
    assert pattern_tokens('') == ()


@pytest.mark.parametrize(
    ('pattern', 'fault'),
    [
        ('', 'is empty'),
        ('  ', 'is empty'),
        ('a\\b', 'backslash'),
        ('/abs', 'relative'),
        ('dir/', 'relative'),
        ('a//b', 'relative'),
        ('**', 'claims every file'),
        ('*', 'claims every file'),
        ('*/**', 'claims every file'),
        ('?', 'claims every file'),
        ('foo**', 'whole path segment'),
        ('**.vtk', 'whole path segment'),
        ('a/**b', 'whole path segment'),
        ('a***', 'whole path segment'),
        ('dir/**', None),
        ('**/x.vtk', None),
        ('a/**/b', None),
        ('a.vtk', None),
    ],
)
def test_check_pattern(pattern, fault):
    """Empty, absolute and wildcard-only patterns are named before they are matched."""
    result = check_pattern(pattern)
    assert (result is None) if fault is None else (fault in result)


# ---------------------------------------------------------------------------
# Licence expressions and forbidden files


@pytest.mark.parametrize(
    ('expression', 'expected'),
    [
        ('MIT', ['MIT']),
        ('CC-BY-4.0 AND LicenseRef-Unknown', ['CC-BY-4.0', 'LicenseRef-Unknown']),
        ('MIT OR Apache-2.0', ['MIT', 'Apache-2.0']),
        ('Apache-2.0 WITH LLVM-exception', ['Apache-2.0']),  # the exception is not a licence
        ('(MIT AND Apache-2.0)', ['MIT', 'Apache-2.0']),
        ('(MIT AND Apache-2.0) OR GPL-2.0+', ['MIT', 'Apache-2.0', 'GPL-2.0+']),
        ('mit or apache-2.0', ['mit', 'apache-2.0']),  # operators are case-insensitive
    ],
)
def test_license_terms(expression, expected):
    """A well-formed expression yields its licence identifiers in order."""
    assert license_terms(expression) == expected


@pytest.mark.parametrize(
    'expression',
    ['MIT AND', 'AND', 'and', 'MIT WITH', 'WITH x', 'OR MIT', '(MIT', 'MIT)', 'MIT AND AND X',
     'CC BY 4.0', 'MIT License', '<fill me>', 'MIT Apache-2.0', '()', 'MIT AND ()', 'MIT+ +'],
)
def test_license_terms_rejects_malformed(expression):
    """Dangling operators, bare operators and illegal characters raise ValueError."""
    with pytest.raises(ValueError):
        license_terms(expression)


def test_known_terms():
    """`known_terms` never raises: malformed and non-string expressions name nothing."""
    assert known_terms('MIT OR Apache-2.0') == ['MIT', 'Apache-2.0']
    assert known_terms('MIT AND') == []
    assert known_terms(3) == []


@pytest.mark.parametrize(
    ('path', 'expected'),
    [
        ('dir/LICENSE', True),
        ('dir/LICENSE.txt', True),
        ('dir/license.md', True),  # the match is case-folded
        ('dir/README.VTK.txt', True),  # a compound name still leads with a forbidden stem
        ('dir/COPYING', True),
        ('dir/CITATION.cff', True),
        ('dir/LICENSE.MIT', True),
        ('dir/COPYING.LESSER', True),
        ('dir/CITATION.bib', True),
        ('dir/licence.htm', True),
        ('dir/NOTICE.pdf', True),
        ('dir/license.json', True),
        ('dir/LICENSE.old', True),
        ('dir/README-VTK', True),
        ('dir/readme_notes.md', True),
        ('dir/mesh.vtk.license', True),  # a REUSE sidecar
        ('dir/.license', True),  # even a bare one
        ('.license', True),
        ('dir/license_plate.stl', False),  # data that merely reads like a licence
        ('dir/notice_field.vtk', False),
        ('dir/copyright_holder.csv', False),
        ('dir/authors.csv', False),
        ('dir/mesh.vtk', False),
        ('.gitattributes', False),
    ],
)
def test_is_forbidden(path, expected):
    """A licence, readme or citation file is rejected whatever follows its name."""
    assert is_forbidden(path) is expected


def test_check_forbidden_files():
    """Every forbidden path is reported, and the remedy names `references` for citations."""
    problems = Problems()
    v.check_forbidden_files(['a/LICENSE.MIT', 'a/data.vtk', 'b/.license', 'CITATION.bib'], problems)
    assert [where for where, _, _ in problems.items] == ['Data/a/LICENSE.MIT', 'Data/b/.license', 'Data/CITATION.bib']
    assert all('`references`' in fix for _, _, fix in problems.items)


# ---------------------------------------------------------------------------
# Small helpers


def test_slugify():
    """A file or directory name becomes a lowercase identifier, never empty."""
    assert slugify('Grey Nurse-Shark.stl') == 'grey_nurse_shark_stl'
    assert slugify('***') == 'new_dataset'


def test_suggested_name():
    """A directory names its group; a root file is named by its stem."""
    assert suggested_name('froggy', ['froggy/frog.mhd']) == 'froggy'
    assert suggested_name('.', ['Bunny.ply']) == 'bunny'


def test_suggested_path():
    """`dir/**` is suggested only for a directory no other dataset reaches."""
    assert suggested_path('d', ['d/a', 'd/b'], set()) == '["d/**"]'
    assert suggested_path('d', ['d/a', 'd/b'], {'d'}) == '["d/a", "d/b"]'
    assert suggested_path('d', ['d/a', 'd/b'], {'d/sub'}) == '["d/a", "d/b"]'
    assert suggested_path('d', ['d/a'], set()) == '["d/a"]'
    assert suggested_path('.', ['a', 'b'], set()) == '["a", "b"]'


def test_type_name_and_dataset_where():
    """Types are named as a contributor writes them; a nameless block is numbered."""
    assert [v._type_name(x) for x in (True, 1, 1.0, 'a', [], {})] == [
        'boolean', 'integer', 'float', 'string', 'array', 'table']
    assert v._dataset_where({'name': 'x'}, 4) == "DATASETS.toml [[dataset]] name = 'x'"
    assert v._dataset_where({'name': 3}, 4) == 'DATASETS.toml [[dataset]] #5'
    assert v._dataset_where({}, 0) == 'DATASETS.toml [[dataset]] #1'


def test_field_missing():
    """Absent, non-string and whitespace-only values are missing."""
    assert field_missing(None) and field_missing('  ') and field_missing(3)
    assert not field_missing('x')


def test_problems_report(capsys):
    """The report lists every problem with its remedy and returns the exit status."""
    problems = Problems()
    assert problems.report() == 0
    assert 'is valid' in capsys.readouterr().out
    problems.add('here', 'what', 'line one\nline two')
    assert problems.report() == 1
    out = capsys.readouterr().out
    assert '1 problem(s)' in out and 'problem: what' in out and 'fix:     line one' in out
    assert 'line two' in out and v.DOCS in out


# ---------------------------------------------------------------------------
# Documents


MINIMAL = """
schema_version = 1

[license."MIT"]
title = "MIT License"
url = "https://opensource.org/licenses/MIT"
commercial_use = true
attribution_required = true
share_alike = false
file = "LICENSES/MIT.txt"
text_source = "https://spdx.org/licenses/MIT.json"

[[dataset]]
name = "thing"
title = "Thing"
description = "A thing."
path = ["thing.vtk"]
SPDX-License-Identifier = "MIT"
provenance = "verified"
origin_url = "https://example.org/thing"
attribution = "Someone."
"""


def _document(*edits: tuple[str, str]) -> dict:
    """Parse `MINIMAL` with literal substitutions applied, each of which must occur once."""
    text = MINIMAL
    for old, new in edits:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    return tomllib.loads(text)


def _dataset_problems(document: dict) -> list[str]:
    """Run check_shape and check_dataset on the first block and return the sentences."""
    problems = Problems()
    check_shape(document, problems)
    check_dataset(document['dataset'][0], 0, document, problems)
    return whats(problems)


def test_minimal_document_passes():
    """The document the rejection tests edit is itself clean."""
    assert _dataset_problems(_document()) == []


@pytest.mark.parametrize(
    ('edits', 'expected'),
    [
        ((('name = "thing"\n', ''),), 'missing required key `name`'),
        ((('title = "Thing"\ndescription', 'title = "Thing"\nextra = 1\ndescription'),), 'unknown key(s): extra'),
        ((('name = "thing"\ntitle = "Thing"', 'title = "Thing"\nname = "thing"'),), '`name` is not the first key'),
        ((('name = "thing"', 'name = "Bad-Name"'),), 'is not a valid identifier'),
        ((('title = "Thing"', 'title = "  "'),), '`title` is empty'),
        ((('description = "A thing."', 'description = ""'),), '`description` is empty'),
        ((('origin_url = "https://example.org/thing"', 'origin_url = " "'),), '`origin_url` is empty'),
        ((('attribution = "Someone."', 'attribution = "   "'),), '`attribution` is empty'),
        ((('path = ["thing.vtk"]', 'path = []'),), '`path` is empty'),
        ((('path = ["thing.vtk"]', 'path = ["thing.vtk", " "]'),), '`path` holds an empty string'),
        ((('path = ["thing.vtk"]', 'path = "thing.vtk"'),), '`path` is a string, not an array'),
        ((('path = ["thing.vtk"]', 'path = ["thing.vtk", 3]'),), '`path` holds a integer, not a string'),
        ((('provenance = "verified"', 'provenance = "guessed"'),), '`provenance` is \'guessed\''),
        ((('"MIT"\nprovenance', '""\nprovenance'),), '`SPDX-License-Identifier` is empty'),
        ((('"MIT"\nprovenance', '"MIT AND"\nprovenance'),), 'not a well-formed expression'),
        ((('"MIT"\nprovenance', '"AND"\nprovenance'),), 'not a well-formed expression'),
        ((('"MIT"\nprovenance', '"MIT License"\nprovenance'),), 'not a well-formed expression'),
        ((('"MIT"\nprovenance', '"(MIT"\nprovenance'),), 'not a well-formed expression'),
        ((('"MIT"\nprovenance', '"GPL-3.0"\nprovenance'),), "names 'GPL-3.0', which has no [license.*] table"),
        ((('"MIT"\nprovenance', '"mit"\nprovenance'),), "'MIT' does"),
        ((('"MIT"\nprovenance', '"FILL-ME-IN"\nprovenance'),), "names 'FILL-ME-IN', which has no"),
        ((('origin_url = "https://example.org/thing"', 'origin_url = "example.org/thing"'),), 'not an http(s) URL'),
        ((('origin_url = "https://example.org/thing"', 'origin_url = "FILL-ME-IN"'),), 'not an http(s) URL'),
        ((('origin_url = "https://example.org/thing"\n', ''),), '`origin_url` is missing'),
        ((('provenance = "verified"', 'provenance = "inferred"'),), '`notes` is required here but is missing'),
        ((('provenance = "verified"', 'provenance = "unknown"'),), '`provenance = "unknown"` but `origin_url` is set'),
        ((('provenance = "verified"', 'provenance = "unknown"'),), '`provenance = "unknown"` but the licence is \'MIT\''),
        ((('provenance = "verified"', 'provenance = "inferred"\nnotes = "  "'),), '`notes` is empty'),
        ((('provenance = "verified"', 'provenance = "verified"\nnotes = 3'),), '`notes` is a integer, not a string'),
        ((('attribution = "Someone."\n', ''),), 'requires attribution but `attribution` is missing'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nmodified = true'),), '`modified = true` but `modification` is missing'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nmodification = "Cropped."'),), '`modification` is set but `modified` is not `true`'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nmodified = false\nmodification = "Cropped."'),), '`modification` is set but `modified` is not `true`'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nmodified = "no"'),), '`modified` is a string, not a boolean'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nmodification = 3\nmodified = true'),), '`modification` is a integer, not a string'),
        ((('attribution = "Someone."', 'attribution = "Someone."\norigin_title = 5'),), '`origin_title` is a integer, not a string'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nredistributed_from = "https://a.org/x"'),), '`redistributed_from` is a string, not an array'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nredistributed_from = [7]'),), '`redistributed_from` holds a integer, not a string'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nredistributed_from = ["a.org/x"]'),), '`redistributed_from` holds \'a.org/x\', which is not an http(s) URL'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nauthors = "x"'),), '`authors` is a string, not an array'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nSPDX-FileCopyrightText = [1]'),), '`SPDX-FileCopyrightText` holds a integer'),
        ((('attribution = "Someone."', 'attribution = "Someone."\ncollection = "nowhere"'),), "`collection` is 'nowhere', which has no [collection.*] table"),
        ((('attribution = "Someone."', 'attribution = "Someone."\ncollection = 3'),), '`collection` is a integer, not a string'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nreferences = "x"'),), '`references` is not an array of tables'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nreferences = [{ doi = "10.1/x" }]'),), 'a `references` entry has no `citation`'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nreferences = [{ citation = 3 }]'),), 'has `citation` as a integer, not a string'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nreferences = [{ citation = " " }]'),), 'has an empty `citation`'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nreferences = [{ citation = "x", DOI = "10.1/x" }]'),), 'unknown key(s): DOI'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nreferences = [{ citation = "x", doi = "https://doi.org/10.1000/x" }]'),), 'is not a bare DOI'),
        ((('attribution = "Someone."', 'attribution = "Someone."\nreferences = [{ citation = "x", url = "example.org" }]'),), 'has `url` \'example.org\', which is not an http(s) URL'),
    ],
)
def test_check_dataset_rejects(edits, expected):
    """Every rule of the field reference rejects a block that breaks it."""
    assert any(expected in what for what in _dataset_problems(_document(*edits))), \
        _dataset_problems(_document(*edits))


def test_redistributed_from_string_fix_shows_the_array_form():
    """The remedy for a string-valued `redistributed_from` is the one-element array."""
    document = _document(('attribution = "Someone."',
                          'attribution = "Someone."\nredistributed_from = "https://a.org/x"'))
    problems = Problems()
    check_shape(document, problems)
    assert 'redistributed_from = ["https://a.org/x"]' in problems.items[0][2]


def test_unknown_provenance_needs_unknown_licence_and_no_origin():
    """A record whose origin is unknown carries `LicenseRef-Unknown` and no `origin_url`."""
    text = MINIMAL.replace('provenance = "verified"\norigin_url = "https://example.org/thing"\nattribution = "Someone."',
                           'provenance = "unknown"\nnotes = "Nothing is known."')
    document = tomllib.loads(text.replace('"MIT"\nprovenance', '"LicenseRef-Unknown"\nprovenance'))
    document['license']['LicenseRef-Unknown'] = dict(document['license']['MIT'], attribution_required=False)
    problems = Problems()
    check_dataset(document['dataset'][0], 0, document, problems)
    assert whats(problems) == []


def test_share_alike_licence_needs_notes():
    """A verified dataset under a share-alike licence must still carry `notes`."""
    document = _document(('share_alike = false', 'share_alike = true'))
    assert '`notes` is required here but is missing' in _dataset_problems(document)
    document['dataset'][0]['notes'] = 'Share-alike: derived work inherits the licence.'
    assert _dataset_problems(document) == []


def test_wrongly_typed_fields_do_not_cascade():
    """A wrongly typed value is reported once, not again as a missing value."""
    document = _document(('provenance = "verified"', 'provenance = "inferred"\nnotes = 3'))
    problems = _dataset_problems(document)
    assert problems == ['`notes` is a integer, not a string']


@pytest.mark.parametrize(
    'malformed',
    [
        'license = ["not-a-table"]',
        'license = 3',
        'collection = ["not-a-table"]',
        '[collection]\nfoo = 1',
        '[collection]\nfoo = "bar"',
        '[license]\nMIT = 1',
        'dataset = "not-an-array"',
        'dataset = [1]',
    ],
)
def test_malformed_tables_are_reported_not_raised(malformed):
    """Every structural error must reach the report and stop the deeper checks."""
    document = tomllib.loads('schema_version = 1\n' + malformed + '\n')
    problems = Problems()

    assert check_shape(document, problems) is False
    check_license_tables(document, problems)
    check_collection_tables(document, problems)
    check_unused_tables(document, problems)

    assert problems.items, f'{malformed!r} produced no problem'


def test_field_type_errors_do_not_stop_the_run():
    """A wrongly typed field is reported, and check_shape still lets the other checks run."""
    document = _document(('attribution = "Someone."', 'attribution = "Someone."\nauthors = "x"'))
    problems = Problems()
    assert check_shape(document, problems) is True
    assert whats(problems) == ['`authors` is a string, not an array']


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('schema_version = 1.0', '`schema_version` is 1.0'),
        ('schema_version = true', '`schema_version` is True'),
        ('schema_version = "1"', "`schema_version` is '1'"),
        ('schema_version = 2', '`schema_version` is 2'),
        ('', '`schema_version` is None'),
        ('schema_version = 1\n[[datasets]]\nname = "x"', 'unknown top-level key(s): datasets'),
    ],
)
def test_check_top_level(text, expected):
    """`schema_version` must be the integer 1 and no other top-level key is allowed."""
    problems = Problems()
    check_top_level(tomllib.loads(text), problems)
    assert whats(problems) == [expected]


def test_check_top_level_accepts_the_format():
    """The four defined top-level keys pass."""
    problems = Problems()
    check_top_level(_document(), problems)
    assert whats(problems) == []


@pytest.mark.parametrize(
    ('edits', 'expected'),
    [
        ((('[license."MIT"]', '[license."MIT"]\nextra = 1'),), 'unknown key(s): extra'),
        ((('title = "MIT License"\n', ''),), 'missing required key `title`'),
        ((('title = "MIT License"', 'title = 3'),), '`title` is a integer, not a string'),
        ((('title = "MIT License"', 'title = " "'),), '`title` is empty'),
        ((('url = "https://opensource.org/licenses/MIT"', 'url = "opensource.org"'),), 'not an http(s) URL'),
        ((('commercial_use = true', 'commercial_use = "yes"'),), '`commercial_use` is a string, not a boolean'),
        ((('file = "LICENSES/MIT.txt"', 'file = "LICENSES/mit-text.txt"'),), 'not "LICENSES/MIT.txt"'),
        ((('file = "LICENSES/MIT.txt"', 'file = "LICENSE"'),), 'not "LICENSES/MIT.txt"'),
        ((('file = "LICENSES/MIT.txt"', 'file = "/etc/hosts"'),), 'not "LICENSES/MIT.txt"'),
        ((('file = "LICENSES/MIT.txt"', 'file = "LICENSES/../LICENSES/MIT.txt"'),), 'not "LICENSES/MIT.txt"'),
        ((('file = "LICENSES/MIT.txt"', 'file = ""'),), '`file` is empty'),
        ((('file = "LICENSES/MIT.txt"', 'file = 3'),), '`file` is a integer, not a string'),
        ((('text_source = "https://spdx.org/licenses/MIT.json"', 'text_source = "  "'),), '`text_source` is empty'),
        ((('text_source = "https://spdx.org/licenses/MIT.json"', 'text_source = true'),), '`text_source` is a boolean'),
        ((('[license."MIT"]', '[license."bad id!"]'), ('"MIT"\nprovenance', '"bad id!"\nprovenance')), 'is not a valid licence identifier'),
    ],
)
def test_check_license_tables_rejects(edits, expected):
    """Every licence-table rule rejects a table that breaks it."""
    document = _document(*edits)
    problems = Problems()
    check_shape(document, problems)
    check_license_tables(document, problems)
    assert any(expected in what for what in whats(problems)), whats(problems)


def test_check_license_tables_needs_the_text_file(tmp_path, monkeypatch):
    """A `file` in the right place must exist."""
    monkeypatch.setattr(v, 'ROOT', tmp_path)
    problems = Problems()
    check_license_tables(_document(), problems)
    assert whats(problems) == ['`file` points at LICENSES/MIT.txt, which does not exist']
    (tmp_path / 'LICENSES').mkdir()
    (tmp_path / 'LICENSES' / 'MIT.txt').write_text('MIT')
    problems = Problems()
    check_license_tables(_document(), problems)
    assert whats(problems) == []


COLLECTION = """
[collection."vtk"]
title = "VTK"
url = "https://vtk.org"
description = "Kitware's toolkit."
"""


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        (COLLECTION + 'extra = 1\n', 'unknown key(s): extra'),
        (COLLECTION.replace('title = "VTK"\n', ''), 'missing required key `title`'),
        (COLLECTION.replace('title = "VTK"', 'title = 5'), '`title` is a integer, not a string'),
        (COLLECTION.replace('title = "VTK"', 'title = ""'), '`title` is empty'),
        (COLLECTION.replace('https://vtk.org', 'vtk.org'), 'not an http(s) URL'),
        ('[collection]\nvtk = 1\n', 'this is a integer, not a table'),
    ],
)
def test_check_collection_tables_rejects(text, expected):
    """Every collection-table rule rejects a table that breaks it."""
    document = tomllib.loads(text)
    problems = Problems()
    check_shape(document, problems)
    check_collection_tables(document, problems)
    assert any(expected in what for what in whats(problems)), whats(problems)


def test_check_collection_tables_accepts():
    """A complete collection table passes."""
    problems = Problems()
    check_collection_tables(tomllib.loads(COLLECTION), problems)
    assert whats(problems) == []


# ---------------------------------------------------------------------------
# Coverage, duplicates, ordering, unused tables


def _coverage(datasets: list[dict], files: list[str]) -> tuple[Problems, dict]:
    """Run check_coverage on bare dataset dicts and return the problems and owners."""
    problems = Problems()
    owners = check_coverage({'dataset': datasets}, files, problems)
    return problems, owners


def test_check_coverage_owners_and_orphans():
    """Owners are recorded once per dataset and uncovered files are named, never `Data/./`."""
    problems, owners = _coverage(
        [{'name': 'a', 'path': ['a/**']}],
        ['a/x.vtk', 'a/sub/y.vtk', 'r1.vtk', 'r2.vtk', 'r3.vtk', 'r4.vtk', 'r5.vtk'],
    )
    assert owners['a/x.vtk'] == ['a'] and owners['a/sub/y.vtk'] == ['a'] and owners['r1.vtk'] == []
    [(where, what, fix)] = problems.items
    assert where == 'Data/r1.vtk, Data/r2.vtk, Data/r3.vtk, Data/r4.vtk, Data/r5.vtk'
    assert 'Data/./' not in where and 'not covered' in what
    assert 'path = ["r1.vtk", "r2.vtk", "r3.vtk", "r4.vtk", "r5.vtk"]' in fix


def test_check_coverage_names_many_orphans():
    """A large group names ten files and counts the rest, with the directory."""
    files = [f'big/f{n:02d}.vtk' for n in range(15)]
    problems, _ = _coverage([], files)
    [(where, _, fix)] = problems.items
    assert where.startswith('Data/big/f00.vtk, ') and 'and 5 more file(s) in Data/big/' in where
    assert 'path = ["big/**"]' in fix
    problems, _ = _coverage([], [f'f{n:02d}.vtk' for n in range(15)])
    assert 'and 5 more file(s) in Data/' in problems.items[0][0]


def test_check_coverage_suggested_block_is_rejected_by_the_validator():
    """The block suggested for an uncovered file cannot be pasted verbatim."""
    problems, _ = _coverage([], ['lonely.vtk'])
    fix = problems.items[0][2]
    block = fix[fix.index('  [[dataset]]'):fix.index('\n\nRead')]
    document = tomllib.loads('\n'.join(line.strip() for line in block.splitlines()))
    document['license'] = _document()['license']
    document['dataset'][0]['path'] = ['lonely.vtk']
    assert document['dataset'][0]['name'] == 'lonely'
    rejected = _dataset_problems(document)
    assert any("names 'FILL-ME-IN'" in what for what in rejected)
    assert any("`provenance` is 'FILL-ME-IN'" in what for what in rejected)
    assert any("`origin_url` is 'FILL-ME-IN'" in what for what in rejected)


def test_check_coverage_does_not_suggest_a_directory_another_dataset_reaches():
    """A partly covered directory gets an explicit file list, not `dir/**`."""
    problems, _ = _coverage([{'name': 'a', 'path': ['d/a.vtk']}], ['d/a.vtk', 'd/b.vtk', 'd/c.vtk'])
    assert 'path = ["d/b.vtk", "d/c.vtk"]' in problems.items[0][2]


def test_check_coverage_self_overlap():
    """Two patterns of one block matching the same file are reported as that, not as two owners."""
    problems, owners = _coverage([{'name': 'a', 'path': ['d/**', 'd/a.vtk']}], ['d/a.vtk', 'd/b.vtk'])
    assert owners['d/a.vtk'] == ['a']
    assert whats(problems) == [
        "`path` pattern 'd/a.vtk' overlaps an earlier pattern of this block on 1 file(s), for example Data/d/a.vtk"]


def test_check_coverage_duplicate_pattern():
    """A pattern listed twice is reported once and does not double the owner."""
    problems, owners = _coverage([{'name': 'a', 'path': ['a.vtk', 'a.vtk']}], ['a.vtk'])
    assert owners['a.vtk'] == ['a']
    assert whats(problems) == ["`path` lists 'a.vtk' more than once"]


def test_check_coverage_multiple_owners():
    """A file two datasets claim names both."""
    problems, owners = _coverage([{'name': 'a', 'path': ['x.vtk']}, {'name': 'b', 'path': ['*.vtk']}], ['x.vtk'])
    assert owners['x.vtk'] == ['a', 'b']
    assert whats(problems) == ['this file is claimed by more than one dataset: a, b']


def test_check_coverage_bad_patterns_do_not_flood():
    """A wildcard-only, empty or absolute pattern is reported once and claims nothing."""
    files = [f'f{n}.vtk' for n in range(50)]
    problems, owners = _coverage(
        [{'name': 'a', 'path': ['**']}, {'name': 'b', 'path': ['']}, {'name': 'c', 'path': ['/f1.vtk']},
         {'name': 'd', 'path': ['*.vtk']}],
        files,
    )
    assert all(own == ['d'] for own in owners.values())
    assert whats(problems) == [
        "`path` pattern '**' claims every file under Data/",
        "`path` pattern '' is empty",
        "`path` pattern '/f1.vtk' is not a relative path: no leading, trailing or doubled `/`",
    ]


def test_check_coverage_unmatched_pattern():
    """A pattern that matches nothing is reported."""
    problems, _ = _coverage([{'name': 'a', 'path': ['gone.vtk', 'here.vtk']}], ['here.vtk'])
    assert whats(problems) == ["`path` pattern 'gone.vtk' matches no tracked file under Data/"]


def test_check_coverage_skips_wrongly_typed_paths():
    """A `path` that is not an array of strings was reported by check_shape and is not matched."""
    problems, owners = _coverage([{'name': 'a', 'path': 'x.vtk'}, {'name': 'b', 'path': [3]}], ['x.vtk'])
    assert owners['x.vtk'] == []
    assert whats(problems) == ['not covered by any [[dataset]] in DATASETS.toml']


def test_check_identical_files():
    """Byte-identical files are compared across every owner, and agreeing copies pass."""
    doc = {'dataset': [
        {'name': 'a', 'SPDX-License-Identifier': 'MIT', 'provenance': 'verified'},
        {'name': 'b', 'SPDX-License-Identifier': 'CC0-1.0', 'provenance': 'verified'},
        {'name': 'c', 'SPDX-License-Identifier': 'MIT', 'provenance': 'inferred'},
    ]}
    blobs = {'x.vtk': 'blob1', 'y.vtk': 'blob1', 'z.vtk': 'blob1', 'w.vtk': 'blob2', 'q.vtk': 'blob2'}
    owners = {'x.vtk': ['a'], 'y.vtk': ['a', 'b'], 'z.vtk': ['c'], 'w.vtk': ['a'], 'q.vtk': ['a']}
    problems = Problems()
    check_identical_files(doc, blobs, owners, problems)
    assert [where for where, _, _ in problems.items] == ['Data/x.vtk, Data/y.vtk, Data/z.vtk'] * 2
    assert whats(problems) == [
        'these files are byte-identical but carry different licences: CC0-1.0, MIT',
        'these files are byte-identical but carry different provenance: inferred, verified',
    ]


def test_check_identical_files_skips_a_block_whose_name_is_not_a_string():
    """A name of the wrong type is reported by the shape check, not by a crash here."""
    doc = {'dataset': [{'name': ['a'], 'SPDX-License-Identifier': 'MIT', 'provenance': 'verified'}]}
    problems = Problems()
    check_identical_files(doc, {'x.vtk': 'b', 'y.vtk': 'b'}, {'x.vtk': ['a'], 'y.vtk': ['a']}, problems)
    assert whats(problems) == []


def test_check_identical_files_ignores_unowned_and_untracked():
    """A file with no owner or outside the owner map contributes no value."""
    doc = {'dataset': [{'name': 'a', 'SPDX-License-Identifier': 'MIT', 'provenance': 'verified'}]}
    problems = Problems()
    check_identical_files(doc, {'x.vtk': 'b', 'y.vtk': 'b', '.hidden': 'b'}, {'x.vtk': ['a'], 'y.vtk': []}, problems)
    assert whats(problems) == []


def test_check_ordering_and_uniqueness():
    """Duplicate names are reported and the sort message names the two blocks out of order."""
    problems = Problems()
    check_ordering_and_uniqueness({'dataset': [{'name': 'a'}, {'name': 'a'}, {'name': 'zz'}, {'name': 'woman'}]}, problems)
    assert whats(problems) == ['this name is used by more than one dataset', '[[dataset]] blocks are not sorted by `name`']
    assert "'woman' follows 'zz' but sorts before it" in problems.items[1][2]
    problems = Problems()
    check_ordering_and_uniqueness({'dataset': [{'name': 'yinyang'}, {'name': 'action'}, {'name': 'bunny'}]}, problems)
    assert "'action' follows 'yinyang'" in problems.items[0][2]
    problems = Problems()
    check_ordering_and_uniqueness({'dataset': [{'name': 'a'}, {'name': 'b'}, {'name': 3}]}, problems)
    assert whats(problems) == []


def test_check_unused_tables():
    """Licences and collections nobody references are reported; malformed expressions count as nothing."""
    document = _document(('[license."MIT"]', COLLECTION + '\n[license."Zlib"]\ntitle = "z"\n\n[license."MIT"]'))
    document['dataset'][0]['SPDX-License-Identifier'] = 'MIT AND'
    problems = Problems()
    check_unused_tables(document, problems)
    assert [where for where, _, _ in problems.items] == [
        'DATASETS.toml [license."Zlib"]', 'DATASETS.toml [license."MIT"]', 'DATASETS.toml [collection."vtk"]']
    document['dataset'][0]['SPDX-License-Identifier'] = 'MIT'
    document['dataset'][0]['collection'] = 'vtk'
    problems = Problems()
    check_unused_tables(document, problems)
    assert whats(problems) == ['no dataset uses this licence']


def test_check_orphan_license_texts(tmp_path, monkeypatch):
    """Any file in LICENSES/ that no table names is reported, whatever its extension."""
    monkeypatch.setattr(v, 'ROOT', tmp_path)
    monkeypatch.setattr(v, 'LICENSES_DIR', tmp_path / 'LICENSES')
    problems = Problems()
    check_orphan_license_texts(_document(), problems)
    assert whats(problems) == []
    (tmp_path / 'LICENSES').mkdir()
    for name in ('MIT.txt', 'Stray.md', 'MIT.txt.bak', '.DS_Store'):
        (tmp_path / 'LICENSES' / name).write_text('x')
    problems = Problems()
    check_orphan_license_texts(_document(), problems)
    assert [where for where, _, _ in problems.items] == ['LICENSES/MIT.txt.bak', 'LICENSES/Stray.md']


# ---------------------------------------------------------------------------
# The git index and main()


def test_index_blobs_and_tracked_data_files():
    """The index lists every tracked path under Data/ with a blob id; dotfiles are not data files."""
    blobs = index_blobs()
    assert len(blobs) > 1000
    assert all(re.fullmatch(r'[0-9a-f]{40,64}', blob) for blob in blobs.values())
    assert '.gitattributes' in blobs
    files = tracked_data_files(blobs)
    assert files == sorted(files)
    assert '.gitattributes' not in files and 'cow.vtp' in files
    assert tracked_data_files({'a/.x': '1', 'b.vtk': '2', 'a.vtk': '3'}) == ['a.vtk', 'b.vtk']


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Point the validator at a fresh git checkout under tmp_path and return a writer for it."""
    monkeypatch.setattr(v, 'ROOT', tmp_path)
    monkeypatch.setattr(v, 'DATASETS_TOML', tmp_path / 'DATASETS.toml')
    monkeypatch.setattr(v, 'LICENSES_DIR', tmp_path / 'LICENSES')
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)

    def write(table: str | bytes, files: dict[str, str] | None = None, licenses: tuple[str, ...] = ('MIT',)) -> None:
        """Write the table, the licence texts and the tracked data files."""
        (tmp_path / 'DATASETS.toml').write_bytes(table if isinstance(table, bytes) else table.encode())
        (tmp_path / 'LICENSES').mkdir(exist_ok=True)
        for key in licenses:
            (tmp_path / 'LICENSES' / f'{key}.txt').write_text(f'{key} text')
        for path, content in (files or {}).items():
            target = tmp_path / 'Data' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        if files:
            subprocess.run(['git', '-C', str(tmp_path), 'add', '-f', 'Data'], check=True)

    return write


def test_main_passes_on_a_valid_repository(repo, capsys):
    """A consistent table, licence text and index give exit 0 and the coverage count."""
    repo(MINIMAL, {'thing.vtk': 'data', '.gitattributes': 'x'})
    assert v.main() == 0
    out = capsys.readouterr().out
    assert 'DATASETS.toml is valid.' in out
    assert '1 datasets cover 1 files under Data/.' in out


def test_main_reports_missing_table(repo, capsys):
    """A missing DATASETS.toml is one sentence, not a traceback."""
    assert v.main() == 1
    assert 'is missing' in capsys.readouterr().out


def test_main_reports_invalid_toml(repo, capsys):
    """A syntax error is reported with the parser's position."""
    repo('schema_version = [\n')
    assert v.main() == 1
    assert 'is not valid TOML' in capsys.readouterr().out


def test_main_reports_non_utf8(repo, capsys):
    """A Latin-1 byte is a report line, not a UnicodeDecodeError."""
    repo(b'# caf\xe9\nschema_version = 1\n')
    assert v.main() == 1
    assert 'is not UTF-8: byte 5' in capsys.readouterr().out


def test_main_accepts_a_byte_order_mark(repo, capsys):
    """A UTF-8 BOM is not reported as a syntax error on line 1."""
    repo(b'\xef\xbb\xbf' + MINIMAL.encode(), {'thing.vtk': 'data'})
    assert v.main() == 0


def test_main_reports_a_non_git_directory(tmp_path, monkeypatch, capsys):
    """Outside a checkout the validator says so instead of raising CalledProcessError."""
    monkeypatch.setattr(v, 'ROOT', tmp_path)
    monkeypatch.setattr(v, 'DATASETS_TOML', tmp_path / 'DATASETS.toml')
    monkeypatch.setattr(v, 'LICENSES_DIR', tmp_path / 'LICENSES')
    (tmp_path / 'DATASETS.toml').write_text(MINIMAL)
    monkeypatch.setenv('GIT_CEILING_DIRECTORIES', str(tmp_path.parent))
    assert v.main() == 1
    out = capsys.readouterr().out
    assert 'Could not list the files git tracks under Data/' in out and 'git checkout' in out


def test_main_reports_a_missing_git_binary(repo, monkeypatch, capsys):
    """Without git on PATH the validator says so instead of raising FileNotFoundError."""
    repo(MINIMAL, {'thing.vtk': 'data'})
    monkeypatch.setenv('PATH', str(v.ROOT / 'nowhere'))
    assert v.main() == 1
    assert 'Could not list the files git tracks under Data/' in capsys.readouterr().out


def test_main_reports_forbidden_dotfile_sidecar(repo, capsys):
    """A bare `.license` sidecar is caught although dotfiles are not data files."""
    repo(MINIMAL, {'thing.vtk': 'data', '.license': 'MIT', 'thing.vtk.license': 'MIT'})
    assert v.main() == 1
    out = capsys.readouterr().out
    assert 'Data/.license' in out and 'Data/thing.vtk.license' in out


def test_main_continues_after_a_field_type_error(repo, capsys):
    """One wrongly typed field does not hide an uncovered file or a bad ordering."""
    table = MINIMAL.replace('attribution = "Someone."', 'attribution = "Someone."\nauthors = "x"')
    repo(table, {'thing.vtk': 'data', 'other.vtk': 'data'})
    assert v.main() == 1
    out = capsys.readouterr().out
    assert '`authors` is a string, not an array' in out and 'Data/other.vtk' in out


# ---------------------------------------------------------------------------
# Whole-table runs


BAD_TABLE = """
schema_version = 1.0
stray = "x"

[license."MIT"]
title = "MIT License"
url = "https://opensource.org/licenses/MIT"
commercial_use = true
attribution_required = true
share_alike = false
file = "LICENSES/MIT.txt"
text_source = "https://spdx.org/licenses/MIT.json"
extra = 1

[license."CC-BY-4.0"]
title = 3
url = "creativecommons.org/licenses/by/4.0/"
commercial_use = "yes"
attribution_required = true
file = "LICENSE"
text_source = "  "

[license."CC-BY-SA-4.0"]
title = "CC BY-SA 4.0"
url = "https://creativecommons.org/licenses/by-sa/4.0/"
commercial_use = true
attribution_required = true
share_alike = true
file = "LICENSES/CC-BY-SA-4.0.txt"
text_source = "https://spdx.org/licenses/CC-BY-SA-4.0.json"

[license."Unused-1.0"]
title = "Unused"
url = "https://example.org/unused"
commercial_use = true
attribution_required = false
share_alike = false
file = "LICENSES/Unused-1.0.txt"
text_source = "Written for this repository."

[collection."vtk"]
title = "VTK"
url = "https://vtk.org"
description = "Kitware's toolkit."
extra = 1

[collection."nobody"]
title = 5
url = "nope"
description = "Unused."

[[dataset]]
name = "alpha"
title = "Alpha"
description = "Root file."
path = ["alpha.vtk", "alpha.vtk", "gone.vtk", "**"]
SPDX-License-Identifier = "MIT AND"
provenance = "guessed"
origin_url = "example.org/alpha"
collection = "vtk"
modified = "no"
notes = 3

[[dataset]]
name = "zeta"
title = "Zeta"
description = "Out of order."
path = ["beta/one.vtk"]
SPDX-License-Identifier = "MIT"
provenance = "verified"
origin_url = "https://example.org/zeta"
attribution = "Zeta."

[[dataset]]
name = "beta"
title = "Beta"
description = "Byte-identical to zeta's file, under another licence."
path = ["beta/two.vtk", "beta/*.vtk"]
SPDX-License-Identifier = "CC-BY-4.0 OR mit"
provenance = "verified"
origin_url = "https://example.org/beta"
attribution = "Beta."
redistributed_from = "https://example.org/mirror"
references = [{ citation = "x", DOI = "https://doi.org/10.1/x" }, { doi = "10.1000/y" }]

[[dataset]]
name = "dup"
title = "Dup"
description = "First of two."
path = ["thing/data.vtk"]
SPDX-License-Identifier = "GPL-3.0"
provenance = "unknown"
origin_url = "https://example.org/dup"
modification = "Cropped."

[[dataset]]
title = "  "
name = "dup"
description = "Second of two, name not first."
path = []
SPDX-License-Identifier = "CC-BY-SA-4.0"
provenance = "verified"
origin_url = "https://example.org/dup2"
attribution = "Dup."
extra = 1

[[dataset]]
name = "Bad-Name"
description = "No title, invalid name, no attribution."
path = ["sub/*.vtk"]
SPDX-License-Identifier = "MIT"
provenance = "inferred"
origin_url = "https://example.org/bad"
modified = true
"""

BAD_BLOBS = {
    'alpha.vtk': 'b1', 'beta/one.vtk': 'b2', 'beta/two.vtk': 'b2', 'thing/data.vtk': 'b3',
    'thing/LICENSE.MIT': 'b4', 'sub/a.vtk': 'b5', 'sub/b.vtk': 'b5', 'sub/.hidden': 'b6',
    'orphan1.vtk': 'b7', 'orphan2.vtk': 'b8', 'orphan3.vtk': 'b9', 'orphan4.vtk': 'b10',
}

BAD_EXPECTED = [
    ('DATASETS.toml', '`schema_version` is 1.0'),
    ('DATASETS.toml', 'unknown top-level key(s): stray'),
    ('Data/thing/LICENSE.MIT', 'per-dataset metadata files are not allowed'),
    ("name = 'alpha'", '`notes` is a integer, not a string'),
    ("name = 'alpha'", '`modified` is a string, not a boolean'),
    ("name = 'beta'", '`redistributed_from` is a string, not an array'),
    ('[license."CC-BY-4.0"]', '`title` is a integer, not a string'),
    ('[license."CC-BY-4.0"]', '`commercial_use` is a string, not a boolean'),
    ('[collection."nobody"]', '`title` is a integer, not a string'),
    ('[license."MIT"]', 'unknown key(s): extra'),
    ('[license."CC-BY-4.0"]', 'missing required key `share_alike`'),
    ('[license."CC-BY-4.0"]', '`text_source` is empty'),
    ('[license."CC-BY-4.0"]', "`url` is 'creativecommons.org/licenses/by/4.0/', which is not an http(s) URL"),
    ('[license."CC-BY-4.0"]', '`file` is \'LICENSE\', not "LICENSES/CC-BY-4.0.txt"'),
    ('[license."CC-BY-SA-4.0"]', '`file` points at LICENSES/CC-BY-SA-4.0.txt, which does not exist'),
    ('[collection."vtk"]', 'unknown key(s): extra'),
    ('[collection."nobody"]', "`url` is 'nope', which is not an http(s) URL"),
    ("name = 'alpha'", "`provenance` is 'guessed'"),
    ("name = 'alpha'", "`SPDX-License-Identifier` 'MIT AND' is not a well-formed expression"),
    ("name = 'alpha'", "`origin_url` is 'example.org/alpha', which is not an http(s) URL"),
    ("name = 'beta'", "names 'mit', which has no [license.*] table; 'MIT' does"),
    ("name = 'beta'", 'a `references` entry has unknown key(s): DOI'),
    ("name = 'beta'", 'a `references` entry has no `citation`'),
    ("name = 'dup'", "names 'GPL-3.0', which has no [license.*] table"),
    ("name = 'dup'", '`notes` is required here but is missing'),
    ("name = 'dup'", '`provenance = "unknown"` but `origin_url` is set'),
    ("name = 'dup'", '`provenance = "unknown"` but the licence is \'GPL-3.0\''),
    ("name = 'dup'", '`modification` is set but `modified` is not `true`'),
    ("name = 'dup'", '`name` is not the first key of the block'),
    ("name = 'dup'", 'unknown key(s): extra'),
    ("name = 'dup'", '`title` is empty'),
    ("name = 'dup'", '`path` is empty, so this dataset claims no file'),
    ("name = 'dup'", '`notes` is required here but is missing'),
    ("name = 'Bad-Name'", 'missing required key `title`'),
    ("name = 'Bad-Name'", "`name` 'Bad-Name' is not a valid identifier"),
    ("name = 'Bad-Name'", '`notes` is required here but is missing'),
    ("name = 'Bad-Name'", '`MIT` requires attribution but `attribution` is missing'),
    ("name = 'Bad-Name'", '`modified = true` but `modification` is missing'),
    ("name = 'dup'", 'this name is used by more than one dataset'),
    ('DATASETS.toml', '[[dataset]] blocks are not sorted by `name`'),
    ("name = 'alpha'", "`path` lists 'alpha.vtk' more than once"),
    ("name = 'alpha'", "`path` pattern 'gone.vtk' matches no tracked file under Data/"),
    ("name = 'alpha'", "`path` pattern '**' claims every file under Data/"),
    ("name = 'beta'", "`path` pattern 'beta/*.vtk' overlaps an earlier pattern of this block on 1 file(s), for example Data/beta/two.vtk"),
    ('Data/orphan1.vtk, Data/orphan2.vtk, Data/orphan3.vtk, Data/orphan4.vtk', 'not covered by any [[dataset]]'),
    ('Data/beta/one.vtk', 'this file is claimed by more than one dataset: beta, zeta'),
    ('Data/beta/one.vtk, Data/beta/two.vtk', 'byte-identical but carry different licences: CC-BY-4.0 OR mit, MIT'),
    ('[license."Unused-1.0"]', 'no dataset uses this licence'),
    ('[collection."nobody"]', 'no dataset uses this collection'),
    ('LICENSES/Stray.md', 'not named by any [license.*] table'),
]


def test_known_bad_table_fails_every_check(tmp_path, monkeypatch):
    """A table breaking every rule produces exactly the expected report, in report order."""
    monkeypatch.setattr(v, 'ROOT', tmp_path)
    monkeypatch.setattr(v, 'LICENSES_DIR', tmp_path / 'LICENSES')
    (tmp_path / 'LICENSES').mkdir()
    for name in ('MIT.txt', 'Unused-1.0.txt', 'Stray.md'):
        (tmp_path / 'LICENSES' / name).write_text('x')
    (tmp_path / 'LICENSE').write_text('root licence')
    problems = Problems()
    check_all(tomllib.loads(BAD_TABLE), BAD_BLOBS, problems)
    found = [(where, what) for where, what, _ in problems.items]
    missing = [pair for pair in BAD_EXPECTED
               if not any(pair[0] in where and pair[1] in what for where, what in found)]
    assert not missing, missing
    assert len(found) == len(BAD_EXPECTED), found
    assert 'Data/./' not in str(found)


def test_published_table_passes(capsys):
    """The whole validator, run on the real repository, reports nothing."""
    started = time.perf_counter()
    status = v.main()
    elapsed = time.perf_counter() - started
    out = capsys.readouterr().out
    assert status == 0, out
    assert 'is valid' in out
    assert elapsed < 2.0, elapsed


def test_published_table_holds_the_documented_invariants():
    """Facts CONTRIBUTING states about the table, checked directly."""
    for entry in PUBLISHED['dataset']:
        if entry['provenance'] == 'unknown':
            assert entry['SPDX-License-Identifier'] == 'LicenseRef-Unknown', entry['name']
            assert 'origin_url' not in entry, entry['name']
    for key, table in PUBLISHED['license'].items():
        assert table['file'] == f'LICENSES/{key}.txt', key


def test_contributing_examples_validate():
    """Every TOML block in CONTRIBUTING.md passes check_dataset against the real tables."""
    blocks = re.findall(r'```toml\n(.*?)```', (ROOT / 'CONTRIBUTING.md').read_text(encoding='utf-8'), re.S)
    assert blocks, 'no TOML examples found'
    checked = 0
    for block in blocks:
        document = tomllib.loads(block)
        context = {
            'license': {**PUBLISHED['license'], **document.get('license', {})},
            'collection': {**PUBLISHED['collection'], **document.get('collection', {})},
        }
        problems = Problems()
        assert check_shape(document, problems)
        check_license_tables(document, problems)
        check_collection_tables(document, problems)
        for index, entry in enumerate(document.get('dataset', [])):
            check_dataset(entry, index, context, problems)
            checked += 1
        assert not problems.items, f'CONTRIBUTING.md example is invalid: {whats(problems)}'
    assert checked == 2
