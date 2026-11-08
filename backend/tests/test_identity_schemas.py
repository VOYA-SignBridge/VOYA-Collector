import pytest
from pydantic import ValidationError

from app.modules.identity.schemas import LoginRequest, RegisterRequest, ResetPasswordRequest


def test_identity_schema_keeps_existing_length_constraints():
    with pytest.raises(ValidationError):
        RegisterRequest(username="ab", email="a@b", password="12345678")

    with pytest.raises(ValidationError):
        LoginRequest(identifier="", password="password")

    with pytest.raises(ValidationError):
        ResetPasswordRequest(token="token", new_password="short")
