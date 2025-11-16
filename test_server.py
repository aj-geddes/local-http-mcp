#!/usr/bin/env python3
"""
Test suite for Local HTTP Bridge MCP Server

Run with: pytest test_server.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from local_http_bridge_mcp import (
    HTTPRequest,
    is_domain_allowed,
    make_http_request,
    detect_content_type,
    format_headers,
)


class TestDomainAllowlist:
    """Test domain allowlist validation"""

    def test_exact_domain_match(self):
        """Test exact domain matching"""
        allowed = ["example.com", "localhost"]
        assert is_domain_allowed("https://example.com/path", allowed)
        assert is_domain_allowed("http://localhost:8080/api", allowed)

    def test_wildcard_domain_match(self):
        """Test wildcard domain matching"""
        allowed = ["*.hvs", "*.local"]
        assert is_domain_allowed("https://apex-demo.hvs/api", allowed)
        assert is_domain_allowed("http://dev.local/", allowed)
        assert is_domain_allowed("https://any-subdomain.hvs/test", allowed)

    def test_domain_rejection(self):
        """Test that non-allowlisted domains are rejected"""
        allowed = ["example.com", "*.hvs"]
        assert not is_domain_allowed("https://evil.com/", allowed)
        assert not is_domain_allowed("https://example.org/", allowed)

    def test_case_insensitive_matching(self):
        """Test that domain matching is case-insensitive"""
        allowed = ["Example.COM", "*.HVS"]
        assert is_domain_allowed("https://example.com/", allowed)
        assert is_domain_allowed("https://test.hvs/", allowed)

    def test_port_handling(self):
        """Test that ports are handled correctly"""
        allowed = ["localhost"]
        assert is_domain_allowed("http://localhost:8080/", allowed)
        assert is_domain_allowed("https://localhost:443/", allowed)


class TestHTTPRequestValidation:
    """Test HTTPRequest Pydantic model validation"""

    def test_valid_request(self):
        """Test creating a valid HTTP request"""
        request = HTTPRequest(
            url="https://example.com/api",
            method="GET",
        )
        assert request.url == "https://example.com/api"
        assert request.method == "GET"
        assert request.verify_ssl is True
        assert request.timeout == 30.0

    def test_invalid_method(self):
        """Test that invalid HTTP methods are rejected"""
        with pytest.raises(ValueError, match="Method must be one of"):
            HTTPRequest(url="https://example.com/", method="INVALID")

    def test_method_case_normalization(self):
        """Test that HTTP methods are normalized to uppercase"""
        request = HTTPRequest(url="https://example.com/", method="get")
        assert request.method == "GET"

    def test_invalid_url_scheme(self):
        """Test that URLs with invalid schemes are rejected"""
        with pytest.raises(ValueError, match="URL must start with http"):
            HTTPRequest(url="ftp://example.com/")

    def test_timeout_validation(self):
        """Test timeout validation"""
        # Valid timeout
        request = HTTPRequest(url="https://example.com/", timeout=60)
        assert request.timeout == 60

        # Invalid timeout (too high)
        with pytest.raises(ValueError, match="Timeout must be between"):
            HTTPRequest(url="https://example.com/", timeout=500)

        # Invalid timeout (negative)
        with pytest.raises(ValueError, match="Timeout must be between"):
            HTTPRequest(url="https://example.com/", timeout=-1)

    def test_optional_parameters(self):
        """Test that optional parameters have correct defaults"""
        request = HTTPRequest(url="https://example.com/")
        assert request.method == "GET"
        assert request.headers is None
        assert request.body is None
        assert request.verify_ssl is True
        assert request.follow_redirects is True


class TestContentTypeDetection:
    """Test content type detection"""

    def test_json_detection(self):
        """Test JSON content type detection"""
        headers = httpx.Headers({"content-type": "application/json"})
        content = b'{"key": "value"}'
        assert detect_content_type(content, headers) == "json"

    def test_text_detection(self):
        """Test text content type detection"""
        headers = httpx.Headers({"content-type": "text/plain"})
        content = b'Hello, world!'
        assert detect_content_type(content, headers) == "text"

    def test_html_detection(self):
        """Test HTML content type detection"""
        headers = httpx.Headers({"content-type": "text/html; charset=utf-8"})
        content = b'<html><body>Hello</body></html>'
        assert detect_content_type(content, headers) == "text"

    def test_binary_detection(self):
        """Test binary content type detection"""
        headers = httpx.Headers({"content-type": "application/octet-stream"})
        content = bytes([0x89, 0x50, 0x4E, 0x47])  # PNG magic bytes
        assert detect_content_type(content, headers) == "binary"

    def test_utf8_fallback_detection(self):
        """Test that valid UTF-8 is detected as text even without content-type"""
        headers = httpx.Headers({})
        content = "Hello, world!".encode('utf-8')
        assert detect_content_type(content, headers) == "text"


class TestHeaderFormatting:
    """Test header formatting and redaction"""

    def test_basic_header_formatting(self):
        """Test basic header conversion"""
        headers = httpx.Headers({
            "content-type": "application/json",
            "x-custom-header": "value"
        })
        result = format_headers(headers)
        assert isinstance(result, dict)
        assert result["content-type"] == "application/json"
        assert result["x-custom-header"] == "value"

    def test_cookie_redaction(self):
        """Test that cookies are redacted"""
        headers = httpx.Headers({
            "set-cookie": "session=abc123; Secure",
            "cookie": "auth=xyz789"
        })
        result = format_headers(headers)
        assert result["set-cookie"] == "[REDACTED]"
        assert result["cookie"] == "[REDACTED]"


class TestHTTPRequest:
    """Test HTTP request execution"""

    @pytest.mark.asyncio
    async def test_successful_get_request(self):
        """Test successful GET request"""
        # Mock httpx response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.content = b'{"status": "ok"}'
        mock_response.text = '{"status": "ok"}'
        mock_response.json.return_value = {"status": "ok"}
        mock_response.url = "https://example.com/api"
        mock_response.elapsed.total_seconds.return_value = 0.123

        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.request.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                request = HTTPRequest(url="https://example.com/api", method="GET")
                result = await make_http_request(request)

                assert result["success"] is True
                assert result["status_code"] == 200
                assert result["body"] == {"status": "ok"}
                assert result["content_type"] == "json"

    @pytest.mark.asyncio
    async def test_domain_not_allowed(self):
        """Test that requests to non-allowlisted domains fail"""
        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            request = HTTPRequest(url="https://evil.com/", method="GET")
            result = await make_http_request(request)

            assert result["success"] is False
            assert "not in the allowlist" in result["error"]
            assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        """Test timeout error handling"""
        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.request.side_effect = httpx.TimeoutException("Timeout")
                mock_client.return_value.__aenter__.return_value = mock_instance

                request = HTTPRequest(url="https://example.com/", method="GET")
                result = await make_http_request(request)

                assert result["success"] is False
                assert "timed out" in result["error"].lower()
                assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test connection error handling"""
        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.request.side_effect = httpx.ConnectError("Connection refused")
                mock_client.return_value.__aenter__.return_value = mock_instance

                request = HTTPRequest(url="https://example.com/", method="GET")
                result = await make_http_request(request)

                assert result["success"] is False
                assert "Could not connect" in result["error"]
                assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_too_many_redirects(self):
        """Test too many redirects error handling"""
        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.request.side_effect = httpx.TooManyRedirects("Too many redirects")
                mock_client.return_value.__aenter__.return_value = mock_instance

                request = HTTPRequest(url="https://example.com/", method="GET")
                result = await make_http_request(request)

                assert result["success"] is False
                assert "Too many redirects" in result["error"]
                assert "troubleshooting" in result

    @pytest.mark.asyncio
    async def test_post_request_with_body(self):
        """Test POST request with body"""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = httpx.Headers({"content-type": "application/json"})
        mock_response.content = b'{"id": 123}'
        mock_response.text = '{"id": 123}'
        mock_response.json.return_value = {"id": 123}
        mock_response.url = "https://example.com/api"
        mock_response.elapsed.total_seconds.return_value = 0.456

        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.request.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                request = HTTPRequest(
                    url="https://example.com/api",
                    method="POST",
                    body='{"name": "test"}',
                    headers={"Content-Type": "application/json"}
                )
                result = await make_http_request(request)

                assert result["success"] is True
                assert result["status_code"] == 201

                # Verify the mock was called with correct parameters
                call_kwargs = mock_instance.request.call_args.kwargs
                assert call_kwargs["method"] == "POST"
                assert call_kwargs["content"] == b'{"name": "test"}'

    @pytest.mark.asyncio
    async def test_response_size_limit(self):
        """Test that oversized responses are rejected"""
        # Create a large response
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB (exceeds 10MB limit)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "text/plain"})
        mock_response.content = large_content
        mock_response.url = "https://example.com/api"

        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.request.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                request = HTTPRequest(url="https://example.com/api", method="GET")
                result = await make_http_request(request)

                assert result["success"] is False
                assert "too large" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_ssl_verification_control(self):
        """Test SSL verification can be disabled"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = httpx.Headers({"content-type": "text/plain"})
        mock_response.content = b"OK"
        mock_response.text = "OK"
        mock_response.url = "https://example.com/"
        mock_response.elapsed.total_seconds.return_value = 0.1

        with patch("local_http_bridge_mcp.ALLOWED_DOMAINS", ["example.com"]):
            with patch("httpx.AsyncClient") as mock_client:
                mock_instance = AsyncMock()
                mock_instance.request.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_instance

                request = HTTPRequest(url="https://example.com/", verify_ssl=False)
                result = await make_http_request(request)

                # Verify AsyncClient was called with verify=False
                assert mock_client.call_args.kwargs["verify"] is False
                assert result["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=local_http_bridge_mcp", "--cov-report=term-missing"])
