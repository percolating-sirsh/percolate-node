"""Verify all critical dependencies are importable."""

import pytest


def test_web_framework_imports():
    """Test FastAPI and Uvicorn imports."""
    from fastapi import FastAPI, Depends, HTTPException
    from fastapi.security import HTTPBearer
    from uvicorn import Config
    assert FastAPI is not None


def test_pydantic_imports():
    """Test Pydantic and Pydantic AI imports."""
    from pydantic import BaseModel, Field
    from pydantic_settings import BaseSettings
    from pydantic_ai import Agent, RunContext
    from pydantic_ai.models import KnownModelName
    assert Agent is not None


def test_mcp_imports():
    """Test FastMCP imports."""
    from fastmcp import FastMCP
    assert FastMCP is not None


def test_auth_crypto_imports():
    """Test JWT and cryptography imports."""
    import jwt
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.backends import default_backend
    assert ec is not None


def test_cli_imports():
    """Test Typer and Rich imports."""
    from typer import Typer
    from rich.console import Console
    from rich.table import Table
    assert Typer is not None


def test_observability_imports():
    """Test OpenTelemetry and Loguru imports."""
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from loguru import logger
    assert trace is not None


def test_database_imports():
    """Test database client imports."""
    import asyncpg
    import redis
    assert asyncpg is not None


def test_utility_imports():
    """Test utility library imports."""
    import httpx
    from dotenv import load_dotenv
    assert httpx is not None


def test_percolate_modules_exist():
    """Test that scaffolded percolate modules are importable."""
    # Agent modules
    from percolate.agents import context, factory, registry
    from percolate.agents.context import AgentContext
    from percolate.agents.factory import create_agent
    from percolate.agents.registry import load_agentlet_schema

    # MCP modules
    from percolate.mcp import server, resources
    from percolate.mcp.server import create_mcp_server
    from percolate.mcp.tools import search, entity, parse, agent

    # Auth modules
    from percolate.auth import models, device, jwt_manager, middleware, oauth
    from percolate.auth.models import Device, AuthToken, TokenPayload
    from percolate.auth.jwt_manager import JWTKeyManager
    from percolate.auth.middleware import verify_token, get_current_tenant

    assert AgentContext is not None
    assert create_agent is not None
    assert create_mcp_server is not None
    assert JWTKeyManager is not None


def test_agent_context_creation():
    """Test AgentContext model instantiation."""
    from percolate.agents.context import AgentContext

    ctx = AgentContext(
        tenant_id="tenant-test",
        user_id="user-123",
        default_model="claude-sonnet-4.5",
    )

    assert ctx.tenant_id == "tenant-test"
    assert ctx.user_id == "user-123"
    assert ctx.default_model == "claude-sonnet-4.5"


def test_agent_context_from_headers():
    """Test AgentContext extraction from HTTP headers."""
    from percolate.agents.context import AgentContext

    headers = {
        "X-User-Id": "user-456",
        "X-Session-Id": "session-789",
        "X-Model-Name": "claude-opus-4",
    }

    ctx = AgentContext.from_headers(headers, tenant_id="tenant-abc")

    assert ctx.tenant_id == "tenant-abc"
    assert ctx.user_id == "user-456"
    assert ctx.session_id == "session-789"
    assert ctx.default_model == "claude-opus-4"


def test_jwt_key_manager_initialization():
    """Test JWTKeyManager can be instantiated."""
    from percolate.auth.jwt_manager import JWTKeyManager

    manager = JWTKeyManager(
        issuer="https://test.percolate.app",
        audience="https://api.test.percolate.app",
    )

    assert manager.issuer == "https://test.percolate.app"
    assert manager.audience == "https://api.test.percolate.app"


def test_auth_models():
    """Test auth model instantiation."""
    from percolate.auth.models import Device, DeviceTrustLevel, TokenType
    from datetime import datetime

    device = Device(
        device_id="device-123",
        public_key="base64encodedkey",
        tenant_id="tenant-456",
        trust_level=DeviceTrustLevel.UNVERIFIED,
    )

    assert device.device_id == "device-123"
    assert device.trust_level == DeviceTrustLevel.UNVERIFIED
    assert isinstance(device.created_at, datetime)
