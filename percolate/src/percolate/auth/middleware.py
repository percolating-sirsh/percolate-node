"""FastAPI authentication middleware."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from percolate.auth.models import TokenPayload
from percolate.auth.jwt_manager import JWTKeyManager

# HTTP Bearer token security scheme
security = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """Verify JWT token and return payload.

    FastAPI dependency that extracts and validates Bearer token
    from Authorization header. Raises 401 if invalid.

    Args:
        credentials: HTTP Bearer token from header

    Returns:
        Validated token payload

    Raises:
        HTTPException: 401 if token invalid or expired

    Example:
        >>> @app.get("/protected")
        >>> async def protected(token: TokenPayload = Depends(verify_token)):
        ...     return {"tenant": token.tenant}
    """
    token = credentials.credentials

    try:
        # Use JWT manager for verification
        jwt_manager = JWTKeyManager()
        payload = await jwt_manager.verify_token(token)

        # Validate required fields
        if not payload.sub or not payload.tenant:
            raise ValueError("Token missing required claims")

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_tenant(
    token: TokenPayload = Depends(verify_token),
) -> str:
    """Extract tenant ID from verified token.

    FastAPI dependency for tenant-scoped endpoints.

    Args:
        token: Validated token payload

    Returns:
        Tenant identifier

    Example:
        >>> @app.get("/data")
        >>> async def get_data(tenant_id: str = Depends(get_current_tenant)):
        ...     return await load_tenant_data(tenant_id)
    """
    return token.tenant


async def require_scope(required_scope: str):
    """Create dependency that requires specific scope.

    Factory for FastAPI dependencies that enforce scope-based
    authorization.

    Args:
        required_scope: Scope required for access

    Returns:
        FastAPI dependency function

    Example:
        >>> @app.delete("/data")
        >>> async def delete_data(
        ...     token: TokenPayload = Depends(require_scope("write"))
        ... ):
        ...     return await delete_tenant_data(token.tenant)
    """
    async def _check_scope(token: TokenPayload = Depends(verify_token)):
        if required_scope not in token.scope:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient scope: {required_scope} required",
            )
        return token

    return _check_scope
