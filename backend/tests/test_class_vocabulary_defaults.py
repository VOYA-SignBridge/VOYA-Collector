"""A newly created class must be born with its vocabulary-schema-v2 cells filled.

An empty recognition_profile is invisible damage: every split filtered by
profile silently omits the class, so it trains nothing and nobody is told. It
happened twice — once for a re-recorded "q", once for all seven diacritic
letters — because class creation never populated the field and a one-off
migration had filled it for the classes that existed at the time.
"""

from __future__ import annotations

import json

import pytest

from app.dataset_manager import (
    _semantic_label_from_slug,
    vocabulary_defaults_for_dialect,
)

CONFIRMED = {
    "bang-chu-cai": {
        "vocabulary_scope": "profile_specific",
        "recognition_profile": "alphabet",
        "vocabulary_group": "fingerspelling_alphabet",
        "motion_type": "static",
    },
    "hoa-de": {
        "vocabulary_scope": "profile_specific",
        "recognition_profile": "hoa_de",
        "vocabulary_group": "hoa_de_vocabulary",
        "motion_type": "dynamic",
    },
}


@pytest.mark.parametrize("dialect,expected", sorted(CONFIRMED.items()))
def test_confirmed_dialect_yields_its_profile(dialect, expected):
    got = vocabulary_defaults_for_dialect(dialect)
    # Mọi khẳng định nằm trong vòng lặp, nên một mục `expected` rỗng trong
    # CONFIRMED sẽ cho ca đó xanh mà không so trường nào.
    assert expected, f"{dialect}: CONFIRMED không nêu trường nào để đối chiếu"
    for key, value in expected.items():
        assert got[key] == value, f"{dialect}.{key}"


def test_dialect_case_and_spacing_do_not_matter():
    assert vocabulary_defaults_for_dialect("  BANG-CHU-CAI  ") == vocabulary_defaults_for_dialect(
        "bang-chu-cai"
    )


def test_an_unconfirmed_dialect_stays_empty_for_manual_review():
    """The mapping's `status: confirmed` gate is the safety property: a dialect
    nobody has classified must not be guessed at."""
    assert vocabulary_defaults_for_dialect("can-tho")["recognition_profile"] == ""
    assert vocabulary_defaults_for_dialect("a-dialect-that-does-not-exist") == {
        "vocabulary_scope": "",
        "recognition_profile": "",
        "vocabulary_group": "",
        "motion_type": "",
        "collection_campaign": "",
    }


def test_every_key_a_class_needs_is_returned():
    got = vocabulary_defaults_for_dialect("bang-chu-cai")
    assert set(got) == {
        "vocabulary_scope",
        "recognition_profile",
        "vocabulary_group",
        "motion_type",
        "collection_campaign",
    }
    assert all(isinstance(v, str) for v in got.values())


def test_mapping_file_stays_readable_and_confirms_the_two_active_dialects():
    """Guards the config the defaults are read from, not just the reader."""
    from app.dataset_manager import _vocabulary_mapping

    mapping = _vocabulary_mapping()
    assert isinstance(mapping, dict)
    for dialect in CONFIRMED:
        assert dialect in mapping, f"{dialect} lost its confirmed mapping entry"
        assert mapping[dialect].get("status") == "confirmed"
        # json round-trip: the entry must be plain data, not something exotic
        json.dumps(mapping[dialect])


@pytest.mark.parametrize(
    "slug,expected", [("cam-on", "cam_on"), ("aa", "aa"), ("cat-dau-ca", "cat_dau_ca"), ("", "")]
)
def test_semantic_label_derives_from_the_slug(slug, expected):
    assert _semantic_label_from_slug(slug) == expected
