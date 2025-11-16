# syntax=docker/dockerfile:1

# Local HTTP Bridge MCP Server - Dockerfile
# Production-ready containerized deployment

FROM python:3.11-slim

# Set metadata
LABEL maintainer="your-email@example.com"
LABEL description="Local HTTP Bridge MCP Server"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r mcp && useradd -r -g mcp mcp

# Set working directory
WORKDIR /app

# Install dependencies first (for better caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir mcp httpx pydantic

# Copy application code
COPY local_http_bridge_mcp.py ./

# Create directory for logs (if needed)
RUN mkdir -p /var/log/local-http-bridge && \
    chown -R mcp:mcp /var/log/local-http-bridge

# Switch to non-root user
USER mcp

# Expose no ports (MCP uses stdio, not network)
# The container communicates via stdin/stdout

# Health check (optional - checks if Python and dependencies are available)
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import mcp; import httpx; import pydantic" || exit 1

# Set the entrypoint
ENTRYPOINT ["python", "local_http_bridge_mcp.py"]

# Default command (can be overridden)
CMD []

# Usage:
# Build: docker build -t local-http-bridge-mcp .
# Run:   docker run -i local-http-bridge-mcp
#
# To access host network (for localhost):
# docker run --network host -i local-http-bridge-mcp
#
# To mount /etc/hosts (for custom DNS):
# docker run -v /etc/hosts:/etc/hosts:ro -i local-http-bridge-mcp
#
# With environment variables:
# docker run --env-file .env -i local-http-bridge-mcp
