# Quick Start Guide - Local HTTP Bridge MCP Server

Get up and running in 5 minutes!

## Prerequisites

- Python 3.10 or higher
- Claude Desktop (or another MCP client)
- Access to private network resources you want to reach

## Step 1: Install Dependencies (1 minute)

```bash
pip install mcp httpx pydantic
```

Or install from the project directory:

```bash
cd local-http-mcp
pip install -e .
```

## Step 2: Configure Your Domains (2 minutes)

Edit `local_http_bridge_mcp.py` and update the `ALLOWED_DOMAINS` list (around line 23):

```python
ALLOWED_DOMAINS = [
    "apex-demo.hvs",      # Your specific domain
    "*.hvs",               # All .hvs subdomains
    "localhost",           # Local development
    "127.0.0.1",          # Localhost IP
    "*.local",             # .local domains
    # Add more as needed
]
```

**Examples**:
- Internal company API: `"api.company.internal"`
- Development server: `"dev.myproject.local"`
- Custom /etc/hosts entry: `"my-app.test"`

## Step 3: Add to Claude Desktop (2 minutes)

### Find Your Config File

**macOS**:
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows**:
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux**:
```
~/.config/Claude/claude_desktop_config.json
```

### Update the Config

Add this to the `mcpServers` section:

```json
{
  "mcpServers": {
    "local-http-bridge": {
      "command": "python",
      "args": ["/absolute/path/to/local_http_bridge_mcp.py"]
    }
  }
}
```

**Important**: Use the **absolute path** to the script!

### Find the Absolute Path

**macOS/Linux**:
```bash
cd local-http-mcp
pwd
# Output: /Users/yourname/projects/local-http-mcp
```

Then use: `/Users/yourname/projects/local-http-mcp/local_http_bridge_mcp.py`

**Windows**:
```powershell
cd local-http-mcp
pwd
# Output: C:\Users\yourname\projects\local-http-mcp
```

Then use: `C:\\Users\\yourname\\projects\\local-http-mcp\\local_http_bridge_mcp.py`

### Full Example Config

```json
{
  "mcpServers": {
    "local-http-bridge": {
      "command": "python",
      "args": ["/Users/yourname/projects/local-http-mcp/local_http_bridge_mcp.py"]
    }
  }
}
```

## Step 4: Restart Claude Desktop

Close and restart Claude Desktop to load the new MCP server.

## Step 5: Test It! (30 seconds)

Open a new conversation in Claude Desktop and try:

```
Check the status of https://apex-demo.hvs/api/health
```

Or:

```
GET https://localhost:8080/api/status
```

### Expected Response

If successful, you'll see something like:

```
I successfully fetched https://apex-demo.hvs/api/health. Here's the response:

Status: 200 OK
Content Type: application/json

{
  "status": "healthy",
  "version": "1.2.3",
  "uptime": 3600
}

The request took 123ms.
```

### Troubleshooting

#### "Domain not in allowlist"

You forgot to add the domain to `ALLOWED_DOMAINS`. Go back to Step 2.

#### "Could not connect"

The server might not be running or reachable. Verify with:

```bash
curl https://apex-demo.hvs/
```

If curl works but the MCP server doesn't, check that `/etc/hosts` is readable by the MCP server.

#### "MCP server not found"

- Check the absolute path in your config is correct
- Make sure Python is in your PATH: `python --version`
- Try using `python3` instead of `python` in the config
- Restart Claude Desktop

#### "Module not found: mcp"

You didn't install the dependencies. Go back to Step 1.

## Common Usage Examples

### Basic GET

```
What's at https://localhost:3000/api/users?
```

### POST with JSON

```
POST this to https://apex-demo.hvs/api/users:
{
  "name": "Alice",
  "email": "alice@example.com"
}
```

### With Authentication

```
Fetch https://api.hvs/protected with header Authorization: Bearer abc123
```

### Self-Signed Certificate

```
Get https://dev.local/ without SSL verification
```

## Advanced Usage

### Custom Timeout

```
Fetch https://slow-api.hvs/data with a 60 second timeout
```

### Custom Headers

```
GET https://api.hvs/data with these headers:
- Authorization: Bearer xyz789
- X-Custom-Header: value
```

### Different HTTP Methods

```
DELETE https://api.hvs/users/123
PUT https://api.hvs/users/123 with body: {"name": "Bob"}
```

## Next Steps

Now that you have it working:

1. **Read PROJECT_SUMMARY.md** for architecture details
2. **Check advanced_config_example.py** for customization options
3. **Run the tests**: `pytest test_server.py -v`
4. **Customize the allowlist** to match your environment
5. **Set up logging** for production use

## Production Deployment

### Docker

```bash
docker build -t local-http-bridge-mcp .
docker run -d --name mcp-bridge \
  -v /etc/hosts:/etc/hosts:ro \
  local-http-bridge-mcp
```

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

Enable and start:

```bash
sudo systemctl enable local-http-bridge
sudo systemctl start local-http-bridge
sudo systemctl status local-http-bridge
```

### Verify It's Running

Check the logs:

```bash
# If running via systemd
sudo journalctl -u local-http-bridge -f

# If running directly
python local_http_bridge_mcp.py
# Look for: "Starting Local HTTP Bridge MCP Server"
```

## Security Checklist

- [ ] Only added necessary domains to `ALLOWED_DOMAINS`
- [ ] Used wildcards sparingly (e.g., `*.hvs` not `*`)
- [ ] Enabled SSL verification for production domains
- [ ] Didn't hardcode sensitive tokens in the config
- [ ] Set appropriate `MAX_RESPONSE_SIZE` for your use case
- [ ] Configured reasonable timeouts

## Getting Help

If you're stuck:

1. **Check the logs**: Look for error messages in the MCP server output
2. **Test directly**: Try `curl` or `httpx` from Python to verify connectivity
3. **Review the tests**: `test_server.py` has many usage examples
4. **Read the docs**: `PROJECT_SUMMARY.md` and `README.md` have detailed info

## What's Next?

You now have a secure bridge between Claude and your private network!

Some ideas for what to build:

- **Internal API Explorer**: Ask Claude to explore your internal APIs
- **Development Helper**: Debug your local development servers
- **Data Analysis**: Fetch data from internal services for analysis
- **Automation**: Script interactions with private APIs
- **Testing**: Use Claude to test your internal endpoints

Happy building!
