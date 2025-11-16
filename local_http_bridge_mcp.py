#!/usr/bin/env python3
"""
Local HTTP Bridge MCP Server

This MCP server acts as a secure bridge for HTTP requests, allowing Claude
to access private network resources (like *.hvs domains) that are only
accessible from your host machine.

Security Features:
- Domain allowlist (prevents unauthorized access)
- SSL verification control
- Request size and timeout limits
- Comprehensive input validation
"""

import asyncio
import fnmatch
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from pydantic import BaseModel, Field, validator

# Configuration
ALLOWED_DOMAINS = [
    "apex-demo.hvs",
    "*.hvs",  # Wildcard for all .hvs domains
    "localhost",
    "127.0.0.1",
    "*.local",  # Common for development
]

DEFAULT_TIMEOUT = 30.0  # seconds
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_REDIRECTS = 5

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("local-http-bridge")


class HTTPRequest(BaseModel):
    """Validated HTTP request parameters"""
    url: str = Field(..., description="Target URL to fetch")
    method: str = Field(default="GET", description="HTTP method")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Custom headers")
    body: Optional[str] = Field(default=None, description="Request body (for POST/PUT/PATCH)")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    timeout: float = Field(default=DEFAULT_TIMEOUT, description="Request timeout in seconds")
    follow_redirects: bool = Field(default=True, description="Follow HTTP redirects")

    @validator("method")
    def validate_method(cls, v):
        allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
        v = v.upper()
        if v not in allowed_methods:
            raise ValueError(f"Method must be one of {allowed_methods}")
        return v

    @validator("timeout")
    def validate_timeout(cls, v):
        if v <= 0 or v > 300:  # Max 5 minutes
            raise ValueError("Timeout must be between 0 and 300 seconds")
        return v

    @validator("url")
    def validate_url(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


def is_domain_allowed(url: str, allowed_domains: List[str]) -> bool:
    """
    Check if the URL's domain is in the allowlist.
    Supports wildcards (e.g., *.hvs)
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or parsed.netloc

    if not hostname:
        return False

    # Normalize hostname (remove port if present)
    hostname = hostname.split(':')[0].lower()

    for pattern in allowed_domains:
        pattern = pattern.lower()
        # Support wildcard matching
        if fnmatch.fnmatch(hostname, pattern):
            logger.info(f"Domain {hostname} matched pattern {pattern}")
            return True
        # Exact match
        if hostname == pattern:
            logger.info(f"Domain {hostname} matched exactly")
            return True

    logger.warning(f"Domain {hostname} not in allowlist")
    return False


def format_headers(headers: httpx.Headers) -> Dict[str, str]:
    """Convert httpx Headers to a simple dict, handling multiple values"""
    result = {}
    for key, value in headers.items():
        # Skip potentially sensitive headers in responses
        if key.lower() in ['set-cookie', 'cookie']:
            result[key] = "[REDACTED]"
        else:
            result[key] = value
    return result


def detect_content_type(content: bytes, headers: httpx.Headers) -> str:
    """Detect if content is JSON, text, or binary"""
    content_type = headers.get("content-type", "").lower()

    if "json" in content_type:
        return "json"
    elif "text" in content_type or "xml" in content_type or "html" in content_type:
        return "text"
    else:
        # Try to decode as text
        try:
            content.decode('utf-8')
            return "text"
        except UnicodeDecodeError:
            return "binary"


async def make_http_request(request: HTTPRequest) -> Dict[str, Any]:
    """
    Execute an HTTP request with proper error handling.

    Returns a structured response with status, headers, and body.
    """
    # Security check: validate domain
    if not is_domain_allowed(request.url, ALLOWED_DOMAINS):
        parsed = urlparse(request.url)
        hostname = parsed.hostname or parsed.netloc
        return {
            "success": False,
            "error": f"Domain '{hostname}' is not in the allowlist",
            "troubleshooting": [
                f"Add '{hostname}' to ALLOWED_DOMAINS in local_http_bridge_mcp.py",
                "Restart the MCP server after making changes",
                "Check that the domain is spelled correctly"
            ]
        }

    # Build request configuration
    async with httpx.AsyncClient(
        verify=request.verify_ssl,
        follow_redirects=request.follow_redirects,
        max_redirects=MAX_REDIRECTS,
        timeout=request.timeout,
    ) as client:
        try:
            logger.info(f"Making {request.method} request to {request.url}")

            # Make the request
            response = await client.request(
                method=request.method,
                url=request.url,
                headers=request.headers or {},
                content=request.body.encode('utf-8') if request.body else None,
            )

            # Check response size
            content_length = len(response.content)
            if content_length > MAX_RESPONSE_SIZE:
                return {
                    "success": False,
                    "error": f"Response too large: {content_length} bytes (max: {MAX_RESPONSE_SIZE})",
                    "troubleshooting": [
                        "Increase MAX_RESPONSE_SIZE in local_http_bridge_mcp.py",
                        "Use pagination or filtering to reduce response size",
                        "Stream the response in chunks"
                    ]
                }

            # Detect content type
            content_type = detect_content_type(response.content, response.headers)

            # Prepare response body
            if content_type == "json":
                try:
                    body = response.json()
                except Exception:
                    body = response.text
            elif content_type == "text":
                body = response.text
            else:
                # Binary content - return base64 or length info
                body = f"[Binary content, {content_length} bytes, content-type: {response.headers.get('content-type')}]"

            logger.info(f"Request successful: {response.status_code} ({content_length} bytes)")

            return {
                "success": True,
                "status_code": response.status_code,
                "headers": format_headers(response.headers),
                "body": body,
                "content_type": content_type,
                "url": str(response.url),  # Final URL after redirects
                "elapsed_ms": response.elapsed.total_seconds() * 1000,
            }

        except httpx.TimeoutException:
            logger.error(f"Request timeout after {request.timeout}s")
            return {
                "success": False,
                "error": f"Request timed out after {request.timeout} seconds",
                "troubleshooting": [
                    "Increase timeout parameter in the request",
                    "Check if the server is responding",
                    "Verify network connectivity to the host"
                ]
            }

        except httpx.ConnectError as e:
            logger.error(f"Connection error: {e}")
            return {
                "success": False,
                "error": f"Could not connect to server: {e}",
                "troubleshooting": [
                    "Verify the URL is correct",
                    "Check that the server is running",
                    "Ensure the domain resolves correctly (check /etc/hosts)",
                    "Verify firewall settings allow the connection"
                ]
            }

        except httpx.TooManyRedirects:
            logger.error("Too many redirects")
            return {
                "success": False,
                "error": f"Too many redirects (max: {MAX_REDIRECTS})",
                "troubleshooting": [
                    "Check for redirect loops on the server",
                    "Increase MAX_REDIRECTS if expected",
                    "Set follow_redirects=false to see the redirect response"
                ]
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error: {e}")
            return {
                "success": False,
                "error": f"HTTP error: {e.response.status_code}",
                "status_code": e.response.status_code,
                "body": e.response.text,
            }

        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}",
                "troubleshooting": [
                    "Check the server logs for more details",
                    "Verify all request parameters are correct",
                    "Try a simpler request to isolate the issue"
                ]
            }


# Initialize MCP server
mcp = Server("local-http-bridge")


@mcp.tool()
async def fetch(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    verify_ssl: bool = True,
    timeout: float = DEFAULT_TIMEOUT,
    follow_redirects: bool = True,
) -> Dict[str, Any]:
    """
    Make an HTTP request to a URL on the local network.

    This tool allows Claude to access private network resources (like *.hvs domains)
    that are only accessible from your host machine. It's ideal for:
    - Internal APIs and services
    - Development servers
    - Private network resources
    - Sites with custom DNS entries in /etc/hosts

    Security: Only domains in the allowlist can be accessed.

    Args:
        url: The target URL (must be in the allowlist)
        method: HTTP method (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)
        headers: Optional custom headers (e.g., {"Authorization": "Bearer token"})
        body: Request body for POST/PUT/PATCH (will be sent as-is)
        verify_ssl: Whether to verify SSL certificates (set to False for self-signed certs)
        timeout: Request timeout in seconds (default: 30, max: 300)
        follow_redirects: Whether to follow HTTP redirects (default: True)

    Returns:
        A dictionary with:
        - success: Whether the request succeeded
        - status_code: HTTP status code (if successful)
        - headers: Response headers
        - body: Response body (parsed as JSON if possible, otherwise text)
        - error: Error message (if failed)
        - troubleshooting: Suggested fixes (if failed)

    Examples:
        fetch("https://apex-demo.hvs/api/health")
        fetch("https://localhost:8080/api/users", method="POST",
              headers={"Content-Type": "application/json"},
              body='{"name": "John"}')
        fetch("https://dev.local/", verify_ssl=False)
    """
    try:
        # Validate and create request
        request = HTTPRequest(
            url=url,
            method=method,
            headers=headers,
            body=body,
            verify_ssl=verify_ssl,
            timeout=timeout,
            follow_redirects=follow_redirects,
        )

        # Execute the request
        result = await make_http_request(request)
        return result

    except ValueError as e:
        # Validation error from Pydantic
        return {
            "success": False,
            "error": f"Invalid request parameters: {str(e)}",
            "troubleshooting": [
                "Check that all parameters are correctly formatted",
                "Ensure the URL starts with http:// or https://",
                "Verify the HTTP method is valid"
            ]
        }


async def main():
    """Run the MCP server"""
    logger.info("Starting Local HTTP Bridge MCP Server")
    logger.info(f"Allowed domains: {ALLOWED_DOMAINS}")

    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
