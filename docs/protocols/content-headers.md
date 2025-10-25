# Content headers

Custom HTTP headers for user context, device information, and content provenance.

## Overview

Percolate supports custom content headers on all API endpoints for:

- **User context**: User ID, email, organization
- **Device context**: Device ID, model, platform, biometric capabilities
- **Authentication**: Tenant ID, session ID, access tokens
- **Content source**: Original document ID, provider, URL
- **Processing context**: Workflow, priority, options
- **Security**: Encryption keys, signatures, audit trails

**Important:** These headers are based on the [p8fs-api content headers specification](https://github.com/p8fs-modules/p8fs-api/blob/main/docs/content_headers.md).

## Header categories

### User context

| Header | Description | Example |
|--------|-------------|---------|
| `X-User-Source-ID` | User identifier | `user-550e8400-e29b-41d4-a716-446655440000` |
| `X-User-Email` | User email | `alice@example.com` |
| `X-User-Name` | Display name | `Alice Smith` |
| `X-User-Role` | Role/permission | `admin`, `editor`, `viewer` |
| `X-User-Organization` | Organization | `Engineering Team` |

### Device context

| Header | Description | Example |
|--------|-------------|---------|
| `X-Device-ID` | Device identifier | `device-abc123def456` |
| `X-Device-Type` | Device type | `mobile`, `desktop`, `tablet`, `iot` |
| `X-Device-Platform` | Operating system | `iOS`, `Android`, `Windows`, `macOS` |
| `X-Device-Version` | OS version | `iOS 17.0`, `Android 13` |
| `X-Device-Model` | Hardware model | `iPhone15,2`, `SM-S918B` |
| `X-App-Version` | Client app version | `1.2.3` |
| `X-Biometric-Available` | Biometric capability | `true`, `false` |
| `X-Secure-Enclave` | Hardware security | `true`, `false` |

### Authentication context

| Header | Description | Example |
|--------|-------------|---------|
| `Authorization` | Bearer token | `Bearer p8fs_at_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...` |
| `X-Tenant-ID` | Tenant scope | `tenant_12345678` |
| `X-Session-ID` | Session identifier | `session_abc123def456` |

### Content source

| Header | Description | Example |
|--------|-------------|---------|
| `X-Content-Source-ID` | Original document ID | `1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms` |
| `X-Content-Source-URL` | Public URL | `https://docs.google.com/document/d/...` |
| `X-Content-Source-Provider` | Source service | `GOOGLE_DRIVE`, `ICLOUD`, `DROPBOX` |
| `X-Content-Source-Type` | Content type | `document`, `spreadsheet`, `image` |

### Processing context

| Header | Description | Example |
|--------|-------------|---------|
| `X-Processing-Context` | Workflow context | `ocr-extraction`, `transcription` |
| `X-Processing-Priority` | Priority level | `high`, `medium`, `low` |
| `X-Chat-Is-Audio` | Audio input flag | `true`, `false` |

## Usage examples

### Mobile app chat request

```http
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer p8fs_at_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-ID: tenant_12345678
X-Session-ID: session_abc123def456
X-Device-ID: device-550e8400-e29b-41d4-a716-446655440000
X-Device-Type: mobile
X-Device-Platform: iOS
X-App-Version: 1.0.0

{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Hello"}],
  "stream": true
}
```

### Document upload with provenance

```http
POST /v1/ingest/upload
Content-Type: multipart/form-data
Authorization: Bearer p8fs_at_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-ID: tenant_12345678
X-Content-Source-Provider: GOOGLE_DRIVE
X-Content-Source-ID: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
X-Content-Source-URL: https://docs.google.com/document/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms

[file data]
```

### Audio chat completion

```http
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer p8fs_at_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-ID: tenant_12345678
X-Session-ID: session_abc123
X-Chat-Is-Audio: true
X-Device-Type: mobile

{
  "model": "gpt-4",
  "messages": [
    {
      "role": "user",
      "content": "UklGRiQFAABXQVZFZm10IBAAAAABAAEA..."  // Base64 WAV
    }
  ],
  "stream": true
}
```

When `X-Chat-Is-Audio: true`, the content is decoded as base64 WAV audio and transcribed before processing.

### High-priority processing

```http
POST /v1/ingest/upload
Content-Type: multipart/form-data
Authorization: Bearer p8fs_at_eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-ID: tenant_12345678
X-Processing-Priority: high
X-Processing-Context: urgent-contract-review

[file data]
```

## Browser vs mobile app

### Key differences

| Aspect | Browser | Mobile App |
|--------|---------|------------|
| User-Agent | Complex Mozilla string | Simple app identifier |
| Custom Headers | ❌ Not available | ✅ Full custom headers |
| Device Info | Limited to User-Agent | Full device details |
| Authentication | Cookies + Bearer tokens | Bearer tokens only |
| CORS Headers | Origin, Referer sent | Usually not sent |

### Mobile app User-Agent

```
P8FS/1.0 iOS/17.2
P8FS/1.0 Android/14.0
```

### Browser User-Agent

```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

## Implementation

### FastAPI middleware

```python
from fastapi import Request

async def extract_device_info(request: Request) -> dict:
    """Extract device information from request headers."""
    headers = request.headers

    # Check for mobile app headers
    if headers.get("x-device-model") or headers.get("x-device-id"):
        return {
            "type": "mobile_app",
            "device_id": headers.get("x-device-id"),
            "platform": headers.get("x-platform"),
            "app_version": headers.get("x-app-version"),
        }

    # Browser (parse User-Agent)
    return {
        "type": "browser",
        "user_agent": headers.get("user-agent", ""),
    }
```

### Tenant context extraction

```python
from fastapi import Request, HTTPException

async def extract_tenant_context(request: Request) -> dict:
    """Extract tenant context from request headers."""
    tenant_id = request.headers.get("x-tenant-id")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    return {
        "tenant_id": tenant_id,
        "session_id": request.headers.get("x-session-id"),
        "user_id": request.headers.get("x-user-source-id"),
    }
```

## Validation

- All headers are optional unless specified
- Headers starting with `X-` are custom headers
- JSON values must be valid JSON strings
- Timestamps in ISO 8601 format (UTC)
- Provider names uppercase with underscores
- Priority levels: `high`, `medium`, `low`

## Security considerations

- Never include sensitive information in headers that might be logged
- Use `Authorization` header for authentication tokens
- Encrypt sensitive device information
- Validate all header values on server side
- Rate limiting based on device/user headers

## See also

- [p8fs-api Content Headers](https://github.com/p8fs-modules/p8fs-api/blob/main/docs/content_headers.md) - Complete specification
- [OAuth 2.1 Flows](../03-auth.md) - Authentication flows
- [Tenant Context Protocol](#tenant-context-protocol) - Gateway coordination
