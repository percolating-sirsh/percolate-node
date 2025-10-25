"""FastAPI authentication dependencies.

Provides dependency injection for authentication using modern FastAPI patterns.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from percolate.auth.providers import OAuthProvider, User
from percolate.auth.provider_factory import get_provider_instance

# Bearer token scheme (auto_error=False allows optional auth)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    provider: Annotated[OAuthProvider | None, Depends(get_provider_instance)],
) -> User | None:
    """Get current authenticated user from bearer token.

    FastAPI dependency that validates bearer tokens using configured provider.
    Returns None if auth disabled or no token provided.
    Raises 401 only if token provided but invalid.

    Args:
        credentials: Bearer token from Authorization header
        provider: Configured OAuth provider (or None if auth disabled)

    Returns:
        User object if authenticated, None if auth disabled or no token

    Raises:
        HTTPException: 401 if token provided but invalid

    Example:
        >>> @router.get("/optional")
        >>> async def optional(user: User | None = Depends(get_current_user)):
        ...     if user:
        ...         return {"user_id": user.user_id}
        ...     return {"message": "anonymous"}
    """
    # Auth disabled - no user context
    if not provider:
        return None

    # Auth enabled but no token provided - return None for optional auth
    if not credentials:
        return None

    # Validate token
    try:
        user = await provider.validate_token(credentials.credentials)
        logger.debug(f"Authenticated user: {user.user_id}")
        return user
    except ValueError as e:
        error_msg = str(e)

        # Handle expired tokens
        if "token_expired" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={
                    "WWW-Authenticate": 'Bearer error="invalid_token", error_description="Token expired"'
                },
            )

        # Handle invalid tokens
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_auth(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    """Require authentication (fail if no user).

    Convenience dependency for endpoints that require auth.
    Always raises 401 if user not authenticated.

    Args:
        user: User from get_current_user dependency

    Returns:
        User object (never None)

    Raises:
        HTTPException: 401 if not authenticated

    Example:
        >>> @router.get("/admin")
        >>> async def admin(user: User = Depends(require_auth)):
        ...     return {"message": f"Welcome {user.name}"}
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# Type aliases for convenience
OptionalUser = Annotated[User | None, Depends(get_current_user)]
RequiredUser = Annotated[User, Depends(require_auth)]
