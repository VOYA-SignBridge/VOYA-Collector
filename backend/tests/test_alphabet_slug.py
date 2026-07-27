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


class TestSingleLetterGuard:
    """A telex sequence slugifies to exactly the slug its own letter produces:
    'aw' -> 'aw' is also what 'Ă' gives. Accepting it would create a class
    labelled with the literal text and then hand it to whoever types Ă properly.
    """

    @pytest.mark.parametrize("letter", sorted(DIACRITICS))
    def test_accepts_the_real_letter(self, letter):
        from app.processing.class_registry import assert_single_alphabet_letter

        assert assert_single_alphabet_letter(letter) == letter
        assert assert_single_alphabet_letter(unicodedata.normalize("NFD", letter)) == letter

    @pytest.mark.parametrize("telex,letter", sorted(DIACRITICS.items(), key=lambda kv: kv[1]))
    def test_rejects_the_telex_sequence_and_names_the_letter(self, telex, letter):
        from app.processing.class_registry import (
            AlphabetLabelError,
            assert_single_alphabet_letter,
        )

        sequence = DIACRITICS[telex]
        with pytest.raises(AlphabetLabelError) as excinfo:
            assert_single_alphabet_letter(sequence)
        # The message must point at the letter the recorder meant.
        assert telex.upper() in str(excinfo.value)

    @pytest.mark.parametrize("bad", ["", "  ", "ab", "xin chao", "a1"])
    def test_rejects_anything_that_is_not_one_letter(self, bad):
        from app.processing.class_registry import (
            AlphabetLabelError,
            assert_single_alphabet_letter,
        )

        with pytest.raises(AlphabetLabelError):
            assert_single_alphabet_letter(bad)

    @pytest.mark.parametrize("letter", sorted(BASE_LETTERS))
    def test_plain_letters_still_pass(self, letter):
        from app.processing.class_registry import assert_single_alphabet_letter

        assert assert_single_alphabet_letter(letter) == letter


class TestSuggestionSearch:
    """Autocomplete must not steer a recorder from Â onto A.

    The recorder types the letter, picks what the box offers, and records. If
    the box offers the base letter, the wrong class is chosen by hand — the same
    collision the slug fix removed, committed one layer up.
    """

    ALPHABET = ["A", "O", "D", "E", "U", "Ă", "Â", "Ô", "Ơ", "Đ", "Ê", "Ư"]

    def _suggest(self, query, labels, alphabet: bool):
        from app.routers.classes import _normalize_alphabet_search, _normalize_search

        normalize = _normalize_alphabet_search if alphabet else _normalize_search
        q = normalize(query)
        return [l for l in sorted(labels) if normalize(l).startswith(q)]

    @pytest.mark.parametrize("letter", ["Ă", "Â", "Ô", "Ơ", "Đ", "Ê", "Ư"])
    def test_a_diacritic_letter_suggests_only_itself(self, letter):
        assert self._suggest(letter, self.ALPHABET, alphabet=True) == [letter]

    @pytest.mark.parametrize("letter", ["A", "O", "D", "E", "U"])
    def test_a_base_letter_does_not_pull_in_its_diacritics(self, letter):
        assert self._suggest(letter, self.ALPHABET, alphabet=True) == [letter]

    def test_case_and_unicode_form_do_not_matter(self):
        decomposed = unicodedata.normalize("NFD", "â")
        assert self._suggest("â", self.ALPHABET, alphabet=True) == ["Â"]
        assert self._suggest(decomposed, self.ALPHABET, alphabet=True) == ["Â"]

    def test_word_signs_keep_the_forgiving_match(self):
        """Typing without diacritics must still find a word sign."""
        words = ["tôm", "rang muối", "cắt đầu cá"]
        assert self._suggest("tom", words, alphabet=False) == ["tôm"]
        assert self._suggest("rang mu", words, alphabet=False) == ["rang muối"]


def test_both_slugify_copies_agree():
    """The two implementations are duplicated; keep them from drifting apart."""
    samples = list(DIACRITICS) + list(BASE_LETTERS) + ["tôm", "rang muối", "Đ", "đ"]
    for text in samples:
        for preserve in (True, False):
            assert registry_slugify(text, preserve_vn_letters=preserve) == manager_slugify(
                text, preserve_vn_letters=preserve
            ), f"copies disagree on {text!r} (preserve_vn_letters={preserve})"
