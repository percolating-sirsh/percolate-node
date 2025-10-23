"""Authentication and authorization for percolate.

This module provides OAuth 2.1 authentication with:
- Device authorization flow (QR codes)
- Ed25519 key operations
- ES256 JWT signing/verification
- FastAPI middleware for token validation
- Well-known discovery endpoints
"""
