"""OAuth provider factory.

Creates and manages authentication provider instances based on configuration.
"""

from loguru import logger

from percolate.auth.providers import OAuthProvider
from percolate.auth.provider_device import DeviceProvider
from percolate.auth.provider_oidc import OIDCProvider
from percolate.settings import settings


def get_auth_provider() -> OAuthProvider | None:
    """Get configured authentication provider.

    Returns provider instance based on settings.auth_provider:
    - 'disabled' or auth_enabled=False: None (auth disabled)
    - 'device': Percolate mobile device provider
    - 'oidc': External OIDC provider

    Returns:
        OAuthProvider instance or None if auth disabled

    Raises:
        ValueError: Invalid or unsupported provider

    Example:
        >>> provider = get_auth_provider()
        >>> if provider:
        ...     user = await provider.validate_token(token)
    """
    # Auth disabled
    if not settings.auth.enabled:
        logger.info("Authentication disabled")
        return None

    provider_name = settings.auth.provider.lower()

    if provider_name == "disabled":
        logger.info("Authentication provider set to 'disabled'")
        return None

    elif provider_name == "device":
        logger.info("Initializing Percolate device authorization provider")
        return DeviceProvider()

    elif provider_name == "oidc":
        logger.info(
            f"Initializing OIDC provider (issuer: {settings.auth.oidc_issuer_url})"
        )
        return OIDCProvider()

    elif provider_name == "dev":
        logger.info("Initializing dev/dummy provider for testing")
        from percolate.auth.provider_dev import DevProvider
        return DevProvider()

    else:
        raise ValueError(
            f"Unsupported auth provider: {provider_name}. "
            f"Valid options: disabled, device, oidc, dev"
        )


# Global provider instance (lazy-initialized)
_provider_instance: OAuthProvider | None = None


def get_provider_instance() -> OAuthProvider | None:
    """Get or create global provider instance.

    Lazy-initializes provider on first call and caches for subsequent calls.
    Use this for dependency injection in FastAPI routes.

    Returns:
        Cached provider instance or None if auth disabled

    Example:
        >>> from fastapi import Depends
        >>> async def endpoint(provider: OAuthProvider = Depends(get_provider_instance)):
        ...     if provider:
        ...         user = await provider.validate_token(token)
    """
    global _provider_instance

    if _provider_instance is None:
        _provider_instance = get_auth_provider()

    return _provider_instance
