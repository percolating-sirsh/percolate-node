"""Dev provider OAuth endpoints for testing.

Simple click-to-confirm authentication for testing MCP login flows.
NOT FOR PRODUCTION.
"""

from typing import Any

from fastapi import APIRouter, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger

from percolate.auth.provider_dev import DevProvider
from percolate.auth.provider_factory import get_provider_instance
from percolate.settings import settings

router = APIRouter(prefix="/oauth/dev", tags=["OAuth Dev Provider"])


def _get_dev_provider() -> DevProvider | None:
    """Get dev provider if configured."""
    if settings.auth.provider != "dev":
        return None

    provider = get_provider_instance()
    if isinstance(provider, DevProvider):
        return provider
    return None


@router.get("/authorize")
async def dev_authorize(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(default="code"),
    state: str | None = Query(default=None),
    scope: str | None = Query(default=None),
) -> HTMLResponse:
    """Dev provider authorization endpoint.

    Shows simple confirmation page for testing.
    No authentication required.

    Args:
        client_id: OAuth client ID
        redirect_uri: Redirect URI after authorization
        response_type: OAuth response type (code)
        state: OAuth state parameter
        scope: Requested scopes (space-separated)

    Returns:
        HTML confirmation page
    """
    provider = _get_dev_provider()
    if not provider:
        return HTMLResponse(
            content="<h1>Error</h1><p>Dev provider not configured</p>",
            status_code=400,
        )

    # Parse scopes
    scope_list = scope.split() if scope else ["read", "write"]

    # Create authorization
    auth = provider.create_authorization(
        redirect_uri=redirect_uri,
        state=state,
        scope=scope_list,
    )

    logger.info(f"Dev authorization initiated: client={client_id}, redirect={redirect_uri}")

    # Simple HTML confirmation page
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Percolate Dev Login</title>
        <style>
            body {{
                font-family: system-ui, -apple-system, sans-serif;
                max-width: 500px;
                margin: 100px auto;
                padding: 20px;
                text-align: center;
            }}
            .card {{
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 30px;
                background: #f9f9f9;
            }}
            h1 {{ color: #333; }}
            .warning {{
                background: #fff3cd;
                border: 1px solid #ffeeba;
                padding: 10px;
                border-radius: 4px;
                margin: 20px 0;
                color: #856404;
            }}
            .info {{
                color: #666;
                font-size: 14px;
                margin: 15px 0;
            }}
            .scope {{
                display: inline-block;
                background: #e3f2fd;
                padding: 4px 8px;
                border-radius: 4px;
                margin: 2px;
                font-size: 13px;
            }}
            button {{
                background: #007bff;
                color: white;
                border: none;
                padding: 12px 30px;
                font-size: 16px;
                border-radius: 4px;
                cursor: pointer;
                margin-top: 20px;
            }}
            button:hover {{
                background: #0056b3;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Percolate Dev Login</h1>
            <div class="warning">
                ⚠️ Dev Provider - Not for production use
            </div>
            <div class="info">
                <p><strong>Client:</strong> {client_id}</p>
                <p><strong>Scopes:</strong> {' '.join(f'<span class="scope">{s}</span>' for s in scope_list)}</p>
            </div>
            <form method="post" action="/oauth/dev/confirm">
                <input type="hidden" name="code" value="{auth['code']}">
                <input type="hidden" name="redirect_uri" value="{redirect_uri}">
                <input type="hidden" name="state" value="{state or ''}">
                <button type="submit">✓ Confirm Login</button>
            </form>
            <p class="info" style="margin-top: 30px; font-size: 12px;">
                This is a test provider that auto-approves without credentials.
            </p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/confirm")
async def dev_confirm(
    code: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(default=""),
) -> RedirectResponse:
    """Confirm authorization (user clicked button).

    Args:
        code: Authorization code
        redirect_uri: Redirect URI
        state: OAuth state parameter

    Returns:
        Redirect to client with authorization code
    """
    provider = _get_dev_provider()
    if not provider:
        return RedirectResponse(
            url=f"{redirect_uri}?error=server_error&error_description=Dev+provider+not+configured",
            status_code=302,
        )

    # Approve authorization
    if not provider.approve_authorization(code):
        return RedirectResponse(
            url=f"{redirect_uri}?error=invalid_request&error_description=Invalid+or+expired+code",
            status_code=302,
        )

    # Build redirect URL with code
    redirect_url = f"{redirect_uri}?code={code}"
    if state:
        redirect_url += f"&state={state}"

    logger.info(f"Dev authorization confirmed: code={code[:8]}...")
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post("/token")
async def dev_token(
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str = Form(default=""),
) -> dict[str, Any]:
    """Token endpoint - exchange code for access token.

    Args:
        grant_type: OAuth grant type (authorization_code)
        code: Authorization code
        redirect_uri: Redirect URI (must match)
        client_id: OAuth client ID

    Returns:
        Access token response
    """
    provider = _get_dev_provider()
    if not provider:
        return {
            "error": "server_error",
            "error_description": "Dev provider not configured",
        }

    if grant_type != "authorization_code":
        return {
            "error": "unsupported_grant_type",
            "error_description": f"Grant type {grant_type} not supported",
        }

    # Exchange code for token
    token_response = provider.exchange_code_for_token(code)
    if not token_response:
        return {
            "error": "invalid_grant",
            "error_description": "Invalid or expired authorization code",
        }

    logger.info(f"Dev token issued: client={client_id}")
    return token_response
