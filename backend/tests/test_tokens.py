"""The two hashing schemes, and the reason they are not one.

`app/tokens.py` exists because a six-digit OTP and a 32-byte link token look
alike at a call site and are not alike at all. These tests pin the difference:
a plain hash for the link token, an HMAC keyed by an out-of-database pepper for
the code, and a hard refusal rather than a silent downgrade when the pepper is
missing.
"""

from __future__ import annotations

import hashlib

import pytest

from app import tokens


class TestLinkTokens:
    def test_token_is_long_and_never_repeats(self):
        minted = {tokens.new_link_token() for _ in range(200)}
        assert len(minted) == 200
        assert all(len(t) >= 40 for t in minted)

    def test_hash_is_plain_sha256(self):
        """Deliberately the same scheme `auth.py` already uses for refresh and
        reset tokens. Changing it would invalidate every live session and reset
        link for no gain — 32 random bytes have no dictionary to search."""
        token = tokens.new_link_token()
        assert tokens.hash_link_token(token) == hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

    def test_hash_is_stable_and_distinct(self):
        a, b = tokens.new_link_token(), tokens.new_link_token()
        assert tokens.hash_link_token(a) == tokens.hash_link_token(a)
        assert tokens.hash_link_token(a) != tokens.hash_link_token(b)


class TestCodes:
    PEPPER = "pepper-for-tests-at-least-32-characters"

    @pytest.fixture(autouse=True)
    def _pepper(self, monkeypatch):
        monkeypatch.setattr(tokens.settings, "otp_pepper", self.PEPPER, raising=False)

    def test_missing_pepper_refuses_instead_of_downgrading(self, monkeypatch):
        """The failure that matters. A fallback to plain SHA-256 here produces a
        system that looks identical from the outside and protects nothing: one
        million digests is a table an attacker builds in under a second."""
        monkeypatch.setattr(tokens.settings, "otp_pepper", "", raising=False)
        with pytest.raises(tokens.PepperMissingError):
            tokens.hash_code("123456", purpose="verify_phone", subject="+84900000000")

    def test_pepper_of_only_whitespace_counts_as_missing(self, monkeypatch):
        monkeypatch.setattr(tokens.settings, "otp_pepper", "   ", raising=False)
        with pytest.raises(tokens.PepperMissingError):
            tokens.hash_code("123456", purpose="verify_phone", subject="x")

    def test_digest_is_not_a_plain_hash_of_the_code(self):
        """If it were, the whole table would be reversible from a dump."""
        digest = tokens.hash_code("123456", purpose="verify_email", subject="a@b.test")
        assert digest != hashlib.sha256(b"123456").hexdigest()

    def test_a_different_pepper_gives_a_different_digest(self, monkeypatch):
        """This is what makes reading the database insufficient."""
        first = tokens.hash_code("123456", purpose="verify_email", subject="a@b.test")
        monkeypatch.setattr(tokens.settings, "otp_pepper", "a-completely-different-pepper-value")
        assert tokens.hash_code("123456", purpose="verify_email", subject="a@b.test") != first

    @pytest.mark.parametrize(
        "purpose_a,subject_a,purpose_b,subject_b",
        [
            pytest.param(
                "verify_email", "a@b.test", "reset_password", "a@b.test",
                id="same-subject-different-purpose",
            ),
            pytest.param(
                "verify_email", "a@b.test", "verify_email", "c@d.test",
                id="same-purpose-different-subject",
            ),
            pytest.param(
                "verify_phone", "+84900000000", "verify_email", "+84900000000",
                id="same-value-different-channel",
            ),
        ],
    )
    def test_domain_separation(self, purpose_a, subject_a, purpose_b, subject_b):
        """The same six digits must not validate across flows.

        Without binding purpose and subject into the message, a code captured
        while verifying an email address would also satisfy a password reset for
        the same account — and a code sent to one person would satisfy the
        challenge issued to another who happened to get the same digits.
        """
        assert tokens.hash_code("123456", purpose=purpose_a, subject=subject_a) != \
               tokens.hash_code("123456", purpose=purpose_b, subject=subject_b)

    def test_separator_cannot_be_smuggled_across_fields(self):
        """`purpose + subject` concatenated without a separator would make
        ("verify", "email:x") and ("verifyemail", ":x") the same message. The
        NUL byte cannot appear in either field, so the split is unambiguous."""
        assert tokens.hash_code("1", purpose="ab", subject="c") != \
               tokens.hash_code("1", purpose="a", subject="bc")

    def test_match_is_true_only_for_the_same_digest(self):
        good = tokens.hash_code("123456", purpose="verify_email", subject="a@b.test")
        bad = tokens.hash_code("123457", purpose="verify_email", subject="a@b.test")
        assert tokens.codes_match(good, good)
        assert not tokens.codes_match(bad, good)

    @pytest.mark.parametrize(
        "candidate,stored",
        [
            pytest.param("", "", id="both-empty"),
            pytest.param("", "x", id="no-candidate"),
            pytest.param("x", "", id="no-stored"),
            pytest.param(None, "x", id="candidate-none"),
            pytest.param("x", None, id="stored-none"),
        ],
    )
    def test_empty_never_matches(self, candidate, stored):
        """`both-empty` is the case that matters and the one this test was
        written to catch: `hmac.compare_digest("", "")` is True, so a challenge
        row whose digest was never written would be satisfied by a caller who
        also supplies nothing. Fail-open reached by two ABSENT values rather
        than by a wrong one — the kind that survives review.
        """
        assert not tokens.codes_match(candidate, stored)
