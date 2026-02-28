"""Tests for URL validation / SSRF prevention."""

import pytest
from shared.utils.url_validator import validate_url, URLValidationError


class TestValidateUrl:
    def test_valid_cloudinary_url(self):
        url = "https://res.cloudinary.com/test/image/upload/v1/photo.jpg"
        assert validate_url(url) == url

    def test_empty_url_raises(self):
        with pytest.raises(URLValidationError, match="empty"):
            validate_url("")

    def test_none_url_raises(self):
        with pytest.raises(URLValidationError):
            validate_url(None)

    def test_ftp_scheme_rejected(self):
        with pytest.raises(URLValidationError, match="scheme"):
            validate_url("ftp://evil.com/payload")

    def test_no_hostname_rejected(self):
        with pytest.raises(URLValidationError, match="hostname"):
            validate_url("http:///no-host")

    def test_disallowed_domain_rejected(self):
        with pytest.raises(URLValidationError, match="allowed domains"):
            validate_url("https://evil.com/image.jpg")
