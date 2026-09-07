"""Tests for the dataset table validator, run with `python -m pytest tools/`."""

from __future__ import annotations

from pathlib import Path
import re
import tomllib

import pytest

from validate_datasets import DATASETS_TOML
from validate_datasets import Problems
from validate_datasets import ROOT
from validate_datasets import check_collection_tables
from validate_datasets import check_dataset
from validate_datasets import check_license_tables
from validate_datasets import check_shape
from validate_datasets import is_forbidden
from validate_datasets import license_terms
from validate_datasets import matches


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
        ('a[bc].vtk', 'a[bc].vtk', True),  # brackets are literal, not a class
        ('a[bc].vtk', 'ab.vtk', False),
    ],
)
def test_matches(pattern, path, expected):
    assert matches(pattern, path) is expected


@pytest.mark.parametrize(
    ('expression', 'expected'),
    [
        ('MIT', ['MIT']),
        ('CC-BY-4.0 AND LicenseRef-Unknown', ['CC-BY-4.0', 'LicenseRef-Unknown']),
        ('MIT OR Apache-2.0', ['MIT', 'Apache-2.0']),
        ('Apache-2.0 WITH LLVM-exception', ['Apache-2.0']),  # the exception is not a licence
        ('(MIT AND Apache-2.0)', ['MIT', 'Apache-2.0']),
    ],
)
def test_license_terms(expression, expected):
    assert license_terms(expression) == expected


@pytest.mark.parametrize(
    ('path', 'expected'),
    [
        ('dir/LICENSE', True),
        ('dir/LICENSE.txt', True),
        ('dir/license.md', True),  # the match is case-folded
        ('dir/README.VTK.txt', True),  # a compound name still leads with a forbidden stem
        ('dir/COPYING', True),
        ('dir/CITATION.cff', True),
        ('dir/license_plate.stl', False),  # data that merely reads like a licence
        ('dir/notice_field.vtk', False),
        ('dir/mesh.vtk', False),
    ],
)
def test_is_forbidden(path, expected):
    assert is_forbidden(path) is expected


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


def _document(**overrides: str) -> dict:
    """Parse `MINIMAL` with literal substitutions applied."""
    text = MINIMAL
    for old, new in overrides.items():
        text = text.replace(old.replace('__', ' = '), new)
    return tomllib.loads(text)


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
    ],
)
def test_malformed_tables_are_reported_not_raised(malformed):
    """Every shape error must reach the report; a traceback tells the contributor nothing."""
    document = tomllib.loads('schema_version = 1\n' + malformed + '\n')
    problems = Problems()

    check_shape(document, problems)
    check_license_tables(document, problems)
    check_collection_tables(document, problems)

    assert problems.items, f'{malformed!r} produced no problem'


def test_empty_license_identifier_is_rejected():
    """An empty expression names no licence, so nothing else can check it."""
    document = tomllib.loads(MINIMAL.replace('"MIT"\nprovenance', '""\nprovenance'))
    problems = Problems()

    check_dataset(document['dataset'][0], 0, document, problems)

    assert any('SPDX-License-Identifier' in what for _, what, _ in problems.items)


def test_contributing_examples_validate():
    """Every TOML block in CONTRIBUTING.md must pass the checks it documents."""
    blocks = re.findall(r'```toml\n(.*?)```', (ROOT / 'CONTRIBUTING.md').read_text(), re.S)
    assert blocks, 'no TOML examples found'

    for block in blocks:
        document = tomllib.loads(block)
        problems = Problems()
        check_license_tables(document, problems)
        check_collection_tables(document, problems)
        assert not problems.items, (
            f'CONTRIBUTING.md example is invalid: {[w for _, w, _ in problems.items]}'
        )


def test_published_table_still_validates():
    """A refactor must not quietly stop checking the real file."""
    document = tomllib.loads(DATASETS_TOML.read_text())
    problems = Problems()

    check_shape(document, problems)
    check_license_tables(document, problems)
    check_collection_tables(document, problems)

    assert not problems.items, [w for _, w, _ in problems.items]


def test_unknown_provenance_carries_no_origin_and_no_licence():
    """Two invariants CONTRIBUTING states and the whole table currently holds."""
    document = tomllib.loads(DATASETS_TOML.read_text())

    for entry in document['dataset']:
        if entry['provenance'] == 'unknown':
            assert entry['SPDX-License-Identifier'] == 'LicenseRef-Unknown', entry['name']
            assert 'origin_url' not in entry, entry['name']


def test_license_file_paths_stay_inside_the_licenses_directory():
    """`file` is resolved and opened, so it must not be able to point anywhere else."""
    document = tomllib.loads(DATASETS_TOML.read_text())

    for key, table in document['license'].items():
        path = Path(table['file'])
        assert not path.is_absolute(), key
        assert path.parts[0] == 'LICENSES', key
        assert '..' not in path.parts, key
