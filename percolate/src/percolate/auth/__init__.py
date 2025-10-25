"""Authentication and authorization for percolate.

This module provides OAuth 2.1 authentication with:
- Device authorization flow (QR codes)
- Ed25519 key operations
- ES256 JWT signing/verification
- FastAPI middleware for token validation
- Well-known discovery endpoints

Supported providers:
- P8FS: Custom mobile device authorization (Ed25519)
- OIDC: External providers (Microsoft, Google, GitHub)
"""

from percolate.auth.providers import OAuthProvider, User
from percolate.auth.provider_factory import get_auth_provider, get_provider_instance
from percolate.auth.dependencies import (
    get_current_user,
    require_auth,
    OptionalUser,
    RequiredUser,
)

__all__ = [
    "OAuthProvider",
    "User",
    "get_auth_provider",
    "get_provider_instance",
    "get_current_user",
    "require_auth",
    "OptionalUser",
    "RequiredUser",
]
