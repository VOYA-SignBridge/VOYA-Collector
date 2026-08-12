"""A sidecar's `user_id` may hold the signer's NAME or the recording ACCOUNT id.

Reading it blindly is how 15 alphabet samples became unresolvable: their sidecar
carries

    {"user_id": "eeeaeb8b-a832-4d1d-bac7-ebdd819fc644", "user": "Minh"}

so the account UUID won over the name, `legacy_name_to_signer_id` had nothing to
match, and those samples then blocked strict signer-disjoint splitting for the
whole profile — the split tool refuses to run while any sample lacks a signer.

The failure was silent: the manifest reported "16 unresolved" and carried on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

np = pytest.importorskip("numpy")  # create_dataset_manifest imports numpy

from create_dataset_manifest import _signer_name  # noqa: E402

ACCOUNT_UUID = "eeeaeb8b-a832-4d1d-bac7-ebdd819fc644"


def test_account_uuid_never_wins_over_a_name():
    """The exact shape of the 15 broken sidecars."""
    assert _signer_name(ACCOUNT_UUID, "Minh") == "Minh"


def test_plain_name_is_taken_from_the_first_field():
    assert _signer_name("Minh", "ignored") == "Minh"


def test_uppercase_uuid_is_still_a_uuid():
    assert _signer_name(ACCOUNT_UUID.upper(), "Minh") == "Minh"


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_blank_candidates_are_skipped(blank):
    assert _signer_name(blank, "Minh") == "Minh"


def test_all_unusable_gives_empty_not_a_uuid():
    """Returning the UUID here would write a fake signer into the manifest and
    make a leaky split look signer-disjoint."""
    assert _signer_name(ACCOUNT_UUID, None, "") == ""


def test_a_name_that_merely_contains_a_uuid_is_kept():
    """Only a value that is ENTIRELY a UUID is rejected — fullmatch, not search."""
    assert _signer_name(f"Minh {ACCOUNT_UUID}", "x") == f"Minh {ACCOUNT_UUID}"
