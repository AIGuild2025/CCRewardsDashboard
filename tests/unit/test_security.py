"""Unit tests for security utilities (password hashing and JWT tokens)."""

from datetime import timedelta
from uuid import uuid4

import pytest
from jose import JWTError

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_id_from_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    """Test password hashing functions."""

    def test_hash_password(self):
        """Test that password is hashed (not stored in plain text)."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        # Hash should not equal plain password
        assert hashed != password
        # Hash should be a non-empty string
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        # Argon2 hashes start with $argon2
        assert hashed.startswith("$argon2")

    def test_verify_password_correct(self):
        """Test that correct password validates successfully."""
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test that incorrect password fails validation."""
        password = "MySecurePassword123!"
        wrong_password = "WrongPassword456!"
        hashed = hash_password(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_same_password_different_hashes(self):
        """Test that hashing same password twice produces different hashes (salt)."""
        password = "MySecurePassword123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        # Hashes should be different due to random salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestJWTTokens:
    """Test JWT token creation and validation."""

    def test_create_access_token(self):
        """Test creating an access token with user ID."""
        user_id = uuid4()
        token = create_access_token(user_id)

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Should be able to decode token
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self):
        """Test creating access token with custom expiration time."""
        user_id = uuid4()
        expires_delta = timedelta(hours=2)
        token = create_access_token(user_id, expires_delta)

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_create_refresh_token(self):
        """Test creating a refresh token."""
        user_id = uuid4()
        token = create_refresh_token(user_id)

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Should be able to decode token
        payload = decode_token(token)
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_decode_valid_token(self):
        """Test decoding a valid token extracts correct user ID."""
        user_id = uuid4()
        token = create_access_token(user_id)

        payload = decode_token(token)
        assert payload["sub"] == str(user_id)

    def test_decode_invalid_token(self):
        """Test that decoding an invalid token raises JWTError."""
        invalid_token = "invalid.token.string"

        with pytest.raises(JWTError):
            decode_token(invalid_token)

    def test_decode_tampered_token(self):
        """Test that decoding a tampered token raises JWTError."""
        user_id = uuid4()
        token = create_access_token(user_id)

        # Tamper with the token by changing a character
        tampered_token = token[:-5] + "XXXXX"

        with pytest.raises(JWTError):
            decode_token(tampered_token)

    def test_get_user_id_from_token(self):
        """Test extracting user ID from token."""
        user_id = uuid4()
        token = create_access_token(user_id)

        extracted_user_id = get_user_id_from_token(token)
        assert extracted_user_id == user_id

    def test_get_user_id_from_invalid_token(self):
        """Test that invalid token raises error when extracting user ID."""
        invalid_token = "invalid.token.string"

        with pytest.raises(JWTError):
            get_user_id_from_token(invalid_token)

    def test_token_type_differentiation(self):
        """Test that access and refresh tokens are differentiated by type."""
        user_id = uuid4()
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"
        # Both should have same user ID
        assert access_payload["sub"] == refresh_payload["sub"]
