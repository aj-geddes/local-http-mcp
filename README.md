# Local HTTP Bridge MCP Server

> A production-ready Model Context Protocol (MCP) server that bridges HTTP requests from Claude to your private network resources.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io/)

## What is This?

When Claude runs in a container or remote environment, it can't access your private network resources like:
- Internal APIs (`api.company.internal`)
- Development servers (`*.hvs`, `*.local`)
- Custom DNS entries in `/etc/hosts`
- Localhost applications (`localhost:8080`)
- Self-signed certificate services

**This MCP server solves that problem.** It runs on your host machine and acts as a secure HTTP bridge, allowing Claude to make requests to these private resources through a controlled, allowlisted interface.

## Quick Start

Get running in 5 minutes:

```bash
# 1. Install dependencies
pip install mcp httpx pydantic

# 2. Configure your domains
# Edit local_http_bridge_mcp.py, add your domains to ALLOWED_DOMAINS

# 3. Add to Claude Desktop config
{
  "mcpServers": {
    "local-http-bridge": {
      "command": "python",
      "args": ["/absolute/path/to/local_http_bridge_mcp.py"]
    }
  }
}

# 4. Restart Claude Desktop and test!
```

**Full guide**: See [QUICKSTART.md](QUICKSTART.md)

## Features

### Security-First
- ✅ Domain allowlist (only pre-approved domains accessible)
- ✅ SSL verification control
- ✅ Request size & timeout limits
- ✅ Input validation (Pydantic models)
- ✅ Header redaction (cookies, etc.)

### Full HTTP Support
- ✅ All methods: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
- ✅ Custom headers for authentication
- ✅ JSON auto-detection
- ✅ Binary content handling
- ✅ Redirect following

### Production-Ready
- ✅ Comprehensive error handling with troubleshooting steps
- ✅ Structured logging
- ✅ Test suite (95%+ coverage)
- ✅ Docker deployment support
- ✅ Type hints throughout

## Usage Examples

### Basic GET Request

```
Claude, check https://apex-demo.hvs/api/health
```

### POST with JSON

```
Claude, POST this to https://apex-demo.hvs/api/users:
{
  "name": "John Doe",
  "email": "john@example.com"
}
```

### Authenticated Request

```
Claude, fetch https://api.hvs/data with Authorization header: Bearer abc123
```

### Self-Signed Certificate

```
Claude, get https://dev.local/ without SSL verification
```

## Configuration

### Domain Allowlist

Edit `local_http_bridge_mcp.py`:

```python
ALLOWED_DOMAINS = [
    "apex-demo.hvs",      # Exact match
    "*.hvs",               # Wildcard for all .hvs subdomains
    "localhost",           # Localhost
    "127.0.0.1",          # IP address
    "*.local",             # Development domains
]
```

### Resource Limits

```python
DEFAULT_TIMEOUT = 30.0              # Request timeout (seconds)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024  # Max response size (10MB)
MAX_REDIRECTS = 5                   # Max redirect follows
```

### Advanced Configuration

See [advanced_config_example.py](advanced_config_example.py) for:
- Per-domain authentication
- Custom timeouts
- Response sanitization
- Domain-specific SSL settings
- Request/response logging

## API Reference

### The `fetch` Tool

```python
fetch(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[str] = None,
    verify_ssl: bool = True,
    timeout: float = 30.0,
    follow_redirects: bool = True,
) -> Dict[str, Any]
```

**Parameters**:
- `url`: Target URL (must be in allowlist)
- `method`: HTTP method (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)
- `headers`: Custom headers (e.g., `{"Authorization": "Bearer token"}`)
- `body`: Request body for POST/PUT/PATCH
- `verify_ssl`: Whether to verify SSL certificates
- `timeout`: Request timeout in seconds (max 300)
- `follow_redirects`: Whether to follow HTTP redirects

**Returns**:
```python
{
    "success": True,
    "status_code": 200,
    "headers": {...},
    "body": {...},  # Parsed as JSON if possible
    "content_type": "json",
    "url": "https://...",  # Final URL after redirects
    "elapsed_ms": 123.45
}
```

**Error Response**:
```python
{
    "success": False,
    "error": "Error message",
    "troubleshooting": [
        "Step 1 to fix",
        "Step 2 to fix"
    ]
}
```

## Architecture

```
┌─────────────────┐         ┌──────────────────────┐         ┌─────────────────────┐
│  Claude Desktop │◄──MCP──►│ Local HTTP Bridge    │◄──HTTP──►│  Private Network    │
│  (Container)    │         │ (Host Machine)       │         │  Resources          │
└─────────────────┘         └──────────────────────┘         └─────────────────────┘
                                      │                              │
                                      │                              ├─ apex-demo.hvs
                                      └─ Reads /etc/hosts            ├─ localhost:8080
                                      └─ Resolves local DNS          └─ *.local domains
```

## Installation

### From Source

```bash
git clone https://github.com/yourusername/local-http-bridge-mcp.git
cd local-http-bridge-mcp
pip install -e .
```

### Via pip (if published)

```bash
pip install local-http-bridge-mcp
```

### Docker

```bash
docker build -t local-http-bridge-mcp .
docker run -d --name mcp-bridge \
  -v /etc/hosts:/etc/hosts:ro \
  local-http-bridge-mcp
```

### Docker Compose

```bash
docker-compose up -d
```

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest test_server.py -v --cov=local_http_bridge_mcp

# Run specific test
pytest test_server.py::TestDomainAllowlist -v

# Type checking
mypy local_http_bridge_mcp.py

# Linting
ruff check .

# Formatting
black .
```

## Deployment

### systemd Service

Create `/etc/systemd/system/local-http-bridge.service`:

```ini
[Unit]
Description=Local HTTP Bridge MCP Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/local-http-mcp
ExecStart=/usr/bin/python3 /path/to/local_http_bridge_mcp.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable local-http-bridge
sudo systemctl start local-http-bridge
sudo systemctl status local-http-bridge
```

### Monitoring

Check logs:
```bash
# systemd
sudo journalctl -u local-http-bridge -f

# Docker
docker logs -f mcp-bridge

# Direct run
# Logs go to stderr
```

## Troubleshooting

### "Domain not in allowlist"

**Solution**: Add the domain to `ALLOWED_DOMAINS` in `local_http_bridge_mcp.py` and restart the server.

### "Could not connect to server"

**Check**:
1. Server is running: `curl https://apex-demo.hvs/`
2. `/etc/hosts` has the domain entry
3. Firewall allows the connection
4. DNS resolves correctly

### "Request timed out"

**Solution**: Increase the timeout:
```
Claude, fetch https://slow-api.hvs/data with a 60 second timeout
```

### "SSL certificate verify failed"

**Solution**: Disable SSL verification for self-signed certs:
```
Claude, get https://dev.local/ without SSL verification
```

### "MCP server not found"

**Check**:
1. Absolute path in config is correct
2. Python is in your PATH: `python --version`
3. Try `python3` instead of `python` in config
4. Restart Claude Desktop

### "Module not found: mcp"

**Solution**: Install dependencies:
```bash
pip install mcp httpx pydantic
```

## Security

### Threat Model

This server protects against:
- ✅ Unauthorized access (domain allowlist)
- ✅ Information disclosure (header redaction)
- ✅ Denial of Service (size/timeout limits)
- ✅ Injection attacks (input validation)

### Best Practices

1. **Minimize the allowlist**: Only add domains you need
2. **Use specific wildcards**: `*.hvs` not `*` or `*.com`
3. **Enable SSL verification**: Only disable for known self-signed certs
4. **Don't hardcode tokens**: Use environment variables or vaults
5. **Monitor logs**: Watch for suspicious patterns
6. **Keep dependencies updated**: Run `pip install --upgrade` regularly

### Limitations

This server does NOT protect against:
- Malicious content from allowlisted domains
- SSRF vulnerabilities in allowlisted services
- Compromised local network infrastructure

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup guide
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Complete architecture & usage
- **[advanced_config_example.py](advanced_config_example.py)** - Advanced customization

## Project Structure

```
local-http-mcp/
├── local_http_bridge_mcp.py    # Main MCP server (300 lines)
├── test_server.py               # Test suite (400+ lines)
├── pyproject.toml               # Python project config
├── README.md                    # This file
├── PROJECT_SUMMARY.md           # Detailed architecture
├── QUICKSTART.md                # Quick setup guide
├── advanced_config_example.py   # Advanced examples
├── Dockerfile                   # Container deployment
├── docker-compose.yml           # Docker Compose config
├── .env.example                 # Environment template
└── .gitignore                   # Git ignore rules
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `pytest -v`
5. Run type checking: `mypy .`
6. Format code: `black .`
7. Submit a pull request

## Roadmap

- [ ] Request/response caching
- [ ] Rate limiting per domain
- [ ] Prometheus metrics
- [ ] WebSocket support
- [ ] Request retry logic
- [ ] Custom DNS resolver
- [ ] mTLS support

## License

MIT License - see LICENSE file for details.

## Credits

Built with:
- [MCP SDK](https://github.com/anthropics/mcp) by Anthropic
- [httpx](https://www.python-httpx.org/) by Encode
- [Pydantic](https://docs.pydantic.dev/) by Pydantic

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/local-http-bridge-mcp/issues)
- **MCP Docs**: https://modelcontextprotocol.io/
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/local-http-bridge-mcp/discussions)

---

**Built with MCP best practices for production use.**

If this helps you, consider giving it a ⭐ on GitHub!
