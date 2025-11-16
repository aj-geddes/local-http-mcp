#!/usr/bin/env python3
"""
Advanced Configuration Example for Local HTTP Bridge MCP Server

This file demonstrates advanced customization patterns including:
- Per-domain authentication
- Custom timeouts by domain
- Response sanitization
- Domain-specific SSL settings
- Request/response logging
- Custom headers injection

To use these patterns:
1. Copy the patterns you need into local_http_bridge_mcp.py
2. Modify the make_http_request() function to use them
3. Update configuration as needed

DO NOT run this file directly - it's for reference only.
"""

import os
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse


# ============================================================================
# PATTERN 1: Per-Domain Authentication
# ============================================================================

# Store auth tokens in environment variables, not in code!
DOMAIN_AUTH_CONFIG = {
    "api.hvs": {
        "type": "bearer",
        "token": os.getenv("API_HVS_TOKEN", ""),
    },
    "apex-demo.hvs": {
        "type": "bearer",
        "token": os.getenv("APEX_DEMO_TOKEN", ""),
    },
    "internal.company.com": {
        "type": "basic",
        "username": os.getenv("INTERNAL_API_USER", ""),
        "password": os.getenv("INTERNAL_API_PASS", ""),
    },
    "custom-api.local": {
        "type": "header",
        "header_name": "X-API-Key",
        "header_value": os.getenv("CUSTOM_API_KEY", ""),
    },
}


def inject_authentication(url: str, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """
    Automatically inject authentication headers based on domain.

    Usage:
        In make_http_request(), before calling httpx:
        headers = inject_authentication(request.url, request.headers)
    """
    headers = headers or {}
    parsed = urlparse(url)
    hostname = parsed.hostname

    if hostname in DOMAIN_AUTH_CONFIG:
        auth_config = DOMAIN_AUTH_CONFIG[hostname]

        if auth_config["type"] == "bearer":
            token = auth_config["token"]
            if token:
                headers["Authorization"] = f"Bearer {token}"
                logging.info(f"Injected Bearer token for {hostname}")

        elif auth_config["type"] == "basic":
            import base64
            username = auth_config["username"]
            password = auth_config["password"]
            if username and password:
                credentials = f"{username}:{password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"
                logging.info(f"Injected Basic auth for {hostname}")

        elif auth_config["type"] == "header":
            header_name = auth_config["header_name"]
            header_value = auth_config["header_value"]
            if header_value:
                headers[header_name] = header_value
                logging.info(f"Injected custom header {header_name} for {hostname}")

    return headers


# ============================================================================
# PATTERN 2: Custom Timeouts by Domain
# ============================================================================

DOMAIN_TIMEOUT_CONFIG = {
    "slow-api.hvs": 120.0,  # 2 minutes for slow APIs
    "fast-api.hvs": 5.0,    # 5 seconds for fast APIs
    "batch-api.hvs": 300.0, # 5 minutes for batch operations
}


def get_timeout_for_domain(url: str, default_timeout: float) -> float:
    """
    Get custom timeout based on domain.

    Usage:
        In make_http_request(), when creating AsyncClient:
        timeout = get_timeout_for_domain(request.url, request.timeout)
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    return DOMAIN_TIMEOUT_CONFIG.get(hostname, default_timeout)


# ============================================================================
# PATTERN 3: Response Sanitization
# ============================================================================

SENSITIVE_HEADERS = [
    "set-cookie",
    "cookie",
    "authorization",
    "x-api-key",
    "x-auth-token",
    "x-csrf-token",
]


def sanitize_response_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """
    Remove or redact sensitive headers from responses.

    Usage:
        In make_http_request(), before returning:
        sanitized_headers = sanitize_response_headers(format_headers(response.headers))
    """
    sanitized = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_HEADERS:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value
    return sanitized


def sanitize_response_body(body: any, content_type: str) -> any:
    """
    Remove sensitive data from response bodies.

    Usage:
        In make_http_request(), before returning body:
        body = sanitize_response_body(body, content_type)
    """
    if content_type != "json" or not isinstance(body, dict):
        return body

    # List of keys that might contain sensitive data
    sensitive_keys = ["password", "secret", "token", "api_key", "private_key", "ssn"]

    def redact_dict(d: dict) -> dict:
        result = {}
        for key, value in d.items():
            if key.lower() in sensitive_keys:
                result[key] = "[REDACTED]"
            elif isinstance(value, dict):
                result[key] = redact_dict(value)
            elif isinstance(value, list):
                result[key] = [redact_dict(item) if isinstance(item, dict) else item for item in value]
            else:
                result[key] = value
        return result

    return redact_dict(body)


# ============================================================================
# PATTERN 4: Domain-Specific SSL Settings
# ============================================================================

DOMAIN_SSL_CONFIG = {
    "dev.local": False,       # Self-signed cert
    "test.local": False,      # Self-signed cert
    "staging.hvs": False,     # Self-signed cert
    "localhost": False,       # No SSL
    "127.0.0.1": False,       # No SSL
}


def should_verify_ssl(url: str, default_verify: bool) -> bool:
    """
    Determine if SSL should be verified for a domain.

    Usage:
        In make_http_request(), when creating AsyncClient:
        verify_ssl = should_verify_ssl(request.url, request.verify_ssl)
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    # Check if there's a specific config for this domain
    if hostname in DOMAIN_SSL_CONFIG:
        return DOMAIN_SSL_CONFIG[hostname]

    # Default behavior
    return default_verify


# ============================================================================
# PATTERN 5: Request/Response Logging
# ============================================================================

# Configure a separate logger for HTTP traffic
http_logger = logging.getLogger("http-traffic")
http_logger.setLevel(logging.INFO)

# Optional: Log to a separate file
# handler = logging.FileHandler("/var/log/local-http-bridge/traffic.log")
# handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
# http_logger.addHandler(handler)


def log_request(method: str, url: str, headers: Optional[Dict[str, str]], body: Optional[str]):
    """
    Log outgoing HTTP requests.

    Usage:
        In make_http_request(), before making the request:
        log_request(request.method, request.url, request.headers, request.body)
    """
    log_entry = {
        "type": "request",
        "method": method,
        "url": url,
        "headers": sanitize_response_headers(headers or {}),
        "body_size": len(body) if body else 0,
    }
    http_logger.info(json.dumps(log_entry))


def log_response(url: str, status_code: int, headers: Dict[str, str], body_size: int, elapsed_ms: float):
    """
    Log HTTP responses.

    Usage:
        In make_http_request(), after receiving response:
        log_response(response.url, response.status_code, response.headers, len(response.content), elapsed)
    """
    log_entry = {
        "type": "response",
        "url": url,
        "status_code": status_code,
        "headers": sanitize_response_headers(headers),
        "body_size": body_size,
        "elapsed_ms": elapsed_ms,
    }
    http_logger.info(json.dumps(log_entry))


# ============================================================================
# PATTERN 6: Custom Headers by Domain
# ============================================================================

DOMAIN_CUSTOM_HEADERS = {
    "api.hvs": {
        "X-API-Version": "v2",
        "X-Client": "local-http-bridge",
    },
    "apex-demo.hvs": {
        "X-Requested-By": "mcp-server",
    },
}


def inject_custom_headers(url: str, headers: Optional[Dict[str, str]]) -> Dict[str, str]:
    """
    Inject custom headers based on domain.

    Usage:
        In make_http_request(), before calling httpx:
        headers = inject_custom_headers(request.url, request.headers)
    """
    headers = headers or {}
    parsed = urlparse(url)
    hostname = parsed.hostname

    if hostname in DOMAIN_CUSTOM_HEADERS:
        custom_headers = DOMAIN_CUSTOM_HEADERS[hostname]
        headers.update(custom_headers)
        logging.info(f"Injected custom headers for {hostname}: {list(custom_headers.keys())}")

    return headers


# ============================================================================
# PATTERN 7: Rate Limiting by Domain
# ============================================================================

from collections import defaultdict
from datetime import datetime, timedelta

# Track request counts per domain
request_counts: Dict[str, list] = defaultdict(list)

DOMAIN_RATE_LIMITS = {
    "api.hvs": {
        "requests": 100,      # Max requests
        "window": 60,         # Time window in seconds
    },
    "slow-api.hvs": {
        "requests": 10,
        "window": 60,
    },
}


def check_rate_limit(url: str) -> tuple[bool, Optional[str]]:
    """
    Check if a request would exceed the rate limit for a domain.

    Returns:
        (allowed, error_message)

    Usage:
        In make_http_request(), before making the request:
        allowed, error = check_rate_limit(request.url)
        if not allowed:
            return {"success": False, "error": error}
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    if hostname not in DOMAIN_RATE_LIMITS:
        return True, None

    config = DOMAIN_RATE_LIMITS[hostname]
    max_requests = config["requests"]
    window_seconds = config["window"]

    # Clean up old requests
    now = datetime.now()
    cutoff = now - timedelta(seconds=window_seconds)
    request_counts[hostname] = [
        timestamp for timestamp in request_counts[hostname]
        if timestamp > cutoff
    ]

    # Check if we're at the limit
    if len(request_counts[hostname]) >= max_requests:
        return False, f"Rate limit exceeded for {hostname}: {max_requests} requests per {window_seconds}s"

    # Record this request
    request_counts[hostname].append(now)
    return True, None


# ============================================================================
# PATTERN 8: Response Transformation
# ============================================================================

def transform_response_for_domain(url: str, body: any, content_type: str) -> any:
    """
    Transform response data based on domain-specific rules.

    Example: Extract specific fields, reformat data, etc.

    Usage:
        In make_http_request(), before returning body:
        body = transform_response_for_domain(request.url, body, content_type)
    """
    parsed = urlparse(url)
    hostname = parsed.hostname

    # Example: Extract only specific fields from API responses
    if hostname == "api.hvs" and content_type == "json" and isinstance(body, dict):
        # If there's a "data" wrapper, unwrap it
        if "data" in body and "meta" in body:
            return body["data"]

    # Example: Flatten nested structures
    if hostname == "complex-api.hvs" and content_type == "json":
        # Custom transformation logic
        pass

    return body


# ============================================================================
# PATTERN 9: Retry Logic
# ============================================================================

import asyncio


async def make_request_with_retry(
    client,
    method: str,
    url: str,
    headers: Dict[str, str],
    content: Optional[bytes],
    max_retries: int = 3,
    backoff_factor: float = 2.0,
):
    """
    Make HTTP request with exponential backoff retry.

    Usage:
        Replace the client.request() call in make_http_request() with:
        response = await make_request_with_retry(
            client, request.method, request.url, headers, content
        )
    """
    import httpx

    for attempt in range(max_retries + 1):
        try:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=content,
            )
            return response

        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == max_retries:
                # Last attempt failed, re-raise
                raise

            # Calculate backoff delay
            delay = backoff_factor ** attempt
            logging.warning(f"Request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
            logging.info(f"Retrying in {delay}s...")
            await asyncio.sleep(delay)


# ============================================================================
# PATTERN 10: Caching
# ============================================================================

from datetime import datetime, timedelta
from typing import Any

# Simple in-memory cache
cache: Dict[str, tuple[Any, datetime]] = {}

CACHE_TTL = {
    "api.hvs": 60,        # Cache for 60 seconds
    "static.hvs": 3600,   # Cache for 1 hour
}


def get_cache_key(method: str, url: str) -> str:
    """Generate a cache key for a request"""
    return f"{method}:{url}"


def get_cached_response(method: str, url: str) -> Optional[Dict[str, Any]]:
    """
    Get cached response if available and not expired.

    Usage:
        In make_http_request(), before making the request:
        cached = get_cached_response(request.method, request.url)
        if cached:
            return cached
    """
    # Only cache GET requests
    if method.upper() != "GET":
        return None

    parsed = urlparse(url)
    hostname = parsed.hostname

    if hostname not in CACHE_TTL:
        return None

    cache_key = get_cache_key(method, url)
    if cache_key in cache:
        response, timestamp = cache[cache_key]
        ttl = CACHE_TTL[hostname]
        if datetime.now() - timestamp < timedelta(seconds=ttl):
            logging.info(f"Cache hit for {url}")
            return response

    return None


def cache_response(method: str, url: str, response: Dict[str, Any]):
    """
    Cache a successful response.

    Usage:
        In make_http_request(), after successful response:
        cache_response(request.method, request.url, result)
    """
    # Only cache successful GET requests
    if method.upper() != "GET" or not response.get("success"):
        return

    parsed = urlparse(url)
    hostname = parsed.hostname

    if hostname in CACHE_TTL:
        cache_key = get_cache_key(method, url)
        cache[cache_key] = (response, datetime.now())
        logging.info(f"Cached response for {url} (TTL: {CACHE_TTL[hostname]}s)")


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================

# Here's how you would integrate these patterns into make_http_request():

"""
async def make_http_request(request: HTTPRequest) -> Dict[str, Any]:
    # 1. Check cache
    cached = get_cached_response(request.method, request.url)
    if cached:
        return cached

    # 2. Check rate limit
    allowed, error = check_rate_limit(request.url)
    if not allowed:
        return {"success": False, "error": error}

    # 3. Inject authentication
    headers = inject_authentication(request.url, request.headers)

    # 4. Inject custom headers
    headers = inject_custom_headers(request.url, headers)

    # 5. Get timeout
    timeout = get_timeout_for_domain(request.url, request.timeout)

    # 6. Determine SSL verification
    verify_ssl = should_verify_ssl(request.url, request.verify_ssl)

    # 7. Log request
    log_request(request.method, request.url, headers, request.body)

    async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
        try:
            # 8. Make request with retry
            response = await make_request_with_retry(
                client,
                request.method,
                request.url,
                headers,
                request.body.encode('utf-8') if request.body else None,
            )

            # 9. Log response
            log_response(
                str(response.url),
                response.status_code,
                format_headers(response.headers),
                len(response.content),
                response.elapsed.total_seconds() * 1000
            )

            # 10. Sanitize headers
            sanitized_headers = sanitize_response_headers(format_headers(response.headers))

            # 11. Parse body
            content_type = detect_content_type(response.content, response.headers)
            if content_type == "json":
                body = response.json()
            else:
                body = response.text

            # 12. Sanitize body
            body = sanitize_response_body(body, content_type)

            # 13. Transform response
            body = transform_response_for_domain(request.url, body, content_type)

            result = {
                "success": True,
                "status_code": response.status_code,
                "headers": sanitized_headers,
                "body": body,
                "content_type": content_type,
                "url": str(response.url),
                "elapsed_ms": response.elapsed.total_seconds() * 1000,
            }

            # 14. Cache the response
            cache_response(request.method, request.url, result)

            return result

        except Exception as e:
            # Handle errors as before
            ...
"""

# ============================================================================
# ENVIRONMENT VARIABLES
# ============================================================================

# Create a .env file with:
"""
# API Tokens
API_HVS_TOKEN=your_token_here
APEX_DEMO_TOKEN=your_token_here

# Basic Auth
INTERNAL_API_USER=username
INTERNAL_API_PASS=password

# API Keys
CUSTOM_API_KEY=your_api_key_here

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/local-http-bridge/traffic.log
"""

# Load with python-dotenv:
"""
from dotenv import load_dotenv
load_dotenv()
"""
