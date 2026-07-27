"""The seven Vietnamese diacritic letters must stay distinct from their base letter.

Ă Â Đ Ê Ô Ơ Ư are separate letters of the fingerspelling alphabet, not accented
variants of A/D/E/O/U — collapsing them merges two classes into one and the
merge is silent: registering "Â" simply returns the existing "a" class.

The trap is Unicode form. Vietnamese input methods emit "Â" either precomposed
(U+00C2) or decomposed (A + U+0302), and a table keyed on one form misses the
other.
"""

from __future__ import annotations

import unicodedata

import pytest

from app.processing.class_registry import slugify as registry_slugify
from app.dataset_manager import slugify as manager_slugify

# letter -> expected telex-style slug
DIACRITICS = {
    "Ă": "aw",
    "Â": "aa",
    "Đ": "dd",
    "Ê": "ee",
    "Ô": "oo",
    "Ơ": "ow",
    "Ư": "uw",
}

BASE_LETTERS = {"A": "a", "D": "d", "E": "e", "O": "o", "U": "u"}

SLUGIFIERS = pytest.mark.parametrize(
    "slugify", [registry_slugify, manager_slugify], ids=["class_registry", "dataset_manager"]
)


@SLUGIFIERS
@pytest.mark.parametrize("letter,expected", sorted(DIACRITICS.items()))
def test_precomposed_letter_keeps_its_own_slug(slugify, letter, expected):
    assert slugify(unicodedata.normalize("NFC", letter), preserve_vn_letters=True) == expected


@SLUGIFIERS
@pytest.mark.parametrize("letter,expected", sorted(DIACRITICS.items()))
def test_decomposed_letter_keeps_its_own_slug(slugify, letter, expected):
    """The regression: a decomposed letter used to collapse into its base."""
    decomposed = unicodedata.normalize("NFD", letter)
    assert slugify(decomposed, preserve_vn_letters=True) == expected


@SLUGIFIERS
@pytest.mark.parametrize("letter,expected", sorted(DIACRITICS.items()))
def test_lowercase_is_accepted_too(slugify, letter, expected):
    assert slugify(letter.lower(), preserve_vn_letters=True) == expected


@SLUGIFIERS
def test_no_diacritic_letter_collides_with_a_base_letter(slugify):
    diacritic_slugs = {
        slugify(letter, preserve_vn_letters=True) for letter in DIACRITICS
    }
    base_slugs = {slugify(letter, preserve_vn_letters=True) for letter in BASE_LETTERS}

    assert not (diacritic_slugs & base_slugs)
    # 7 letters, 7 distinct slugs — no two diacritics share one either.
    assert len(diacritic_slugs) == len(DIACRITICS)


@SLUGIFIERS
@pytest.mark.parametrize("letter,expected", sorted(BASE_LETTERS.items()))
def test_base_letters_are_unaffected(slugify, letter, expected):
    assert slugify(letter, preserve_vn_letters=True) == expected


@SLUGIFIERS
def test_word_signs_still_strip_diacritics(slugify):
    """Only the alphabet needs this: the sign for "tôm" does not depend on tone."""
    assert slugify("tôm") == "tom"
    assert slugify("rang muối") == "rang-muoi"
    assert slugify("cắt đầu cá") == "cat-dau-ca"


def test_both_slugify_copies_agree():
    """The two implementations are duplicated; keep them from drifting apart."""
    samples = list(DIACRITICS) + list(BASE_LETTERS) + ["tôm", "rang muối", "Đ", "đ"]
    for text in samples:
        for preserve in (True, False):
            assert registry_slugify(text, preserve_vn_letters=preserve) == manager_slugify(
                text, preserve_vn_letters=preserve
            ), f"copies disagree on {text!r} (preserve_vn_letters={preserve})"
