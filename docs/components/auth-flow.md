# Authentication Flow Component Design

## Responsibility

Implement OAuth 2.1 authentication with mobile-first cryptography, device registration, and token management.

## Components

### 1. Device Registration (Mobile)

**Flow:**
```
Mobile App
  → Generate Ed25519 keypair (secure enclave)
  → POST /api/v1/auth/register
    { public_key, device_name, platform }
  ← Server returns verification_code_id
  → Server sends email with 6-digit code
  → User enters code in app
  → Sign verification: signature = Ed25519.sign(verification_code_id, private_key)
  → POST /api/v1/auth/verify
    { verification_code_id, verification_code, signature }
  ← Server validates signature with public_key
  ← Server creates tenant, device, returns OAuth tokens
    { access_token, refresh_token, tenant_id, device_id }
```

**Implementation:**
```python
# Python API endpoint
@router.post("/auth/register")
async def register_device(request: DeviceRegistrationRequest) -> DeviceRegistrationResponse:
    # Validate public key format (Ed25519)
    validate_ed25519_public_key(request.public_key)

    # Create verification code
    code = generate_verification_code()  # 6 digits
    code_id = uuid4()

    # Store pending registration
    await redis.setex(
        f"verification:{code_id}",
        300,  # 5 minutes
        json.dumps({"public_key": request.public_key, "code": code})
    )

    # Send email
    await send_verification_email(request.email, code)

    return {"verification_code_id": str(code_id)}

@router.post("/auth/verify")
async def verify_device(request: DeviceVerificationRequest) -> TokenResponse:
    # Load pending registration
    data = await redis.get(f"verification:{request.verification_code_id}")

    # Verify code
    if data["code"] != request.verification_code:
        raise HTTPException(401, "Invalid verification code")

    # Verify signature (Rust crypto)
    is_valid = verify_ed25519_signature(
        message=request.verification_code_id.encode(),
        signature=request.signature,
        public_key=data["public_key"]
    )
    if not is_valid:
        raise HTTPException(401, "Invalid signature")

    # Create tenant and device
    tenant = await create_tenant(request.email)
    device = await create_device(tenant.id, data["public_key"], request.device_name)

    # Issue OAuth tokens
    tokens = issue_tokens(tenant.id, device.id)

    return tokens
```

**Rust Crypto:**
```rust
// percolate-core/src/crypto/keys.rs
use ed25519_dalek::{PublicKey, Signature, Verifier};

#[pyfunction]
pub fn verify_ed25519_signature(
    message: &[u8],
    signature: &[u8],
    public_key: &[u8]
) -> PyResult<bool> {
    let public_key = PublicKey::from_bytes(public_key)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

    let signature = Signature::from_bytes(signature)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;

    Ok(public_key.verify(message, &signature).is_ok())
}
```

### 2. Device Code Flow (Desktop Pairing)

**Flow:**
```
Desktop App
  → POST /oauth/device/code
    { client_id: "percolate-cli" }
  ← Server returns
    { device_code, user_code, verification_uri, interval: 5 }
  → Display QR code with verification_uri + user_code

Mobile App
  → Scan QR code
  → POST /oauth/device/approve
    { user_code }
    Authorization: Bearer <mobile_access_token>
  ← Server associates device_code with authenticated user

Desktop App
  → Poll POST /oauth/token every 5 seconds
    { grant_type: "urn:ietf:params:oauth:grant-type:device_code",
      device_code,
      client_id }
  ← Server returns tokens once approved
    { access_token, refresh_token }
```

**Implementation:**
```python
@router.post("/oauth/device/code")
async def device_authorization(request: DeviceCodeRequest) -> DeviceCodeResponse:
    device_code = generate_secure_token()
    user_code = generate_user_code()  # e.g., "ABCD-1234"

    await redis.setex(
        f"device_code:{device_code}",
        600,  # 10 minutes
        json.dumps({"user_code": user_code, "client_id": request.client_id})
    )

    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": "https://percolate.app/activate",
        "interval": 5
    }

@router.post("/oauth/device/approve")
async def approve_device(
    request: DeviceApprovalRequest,
    user: User = Depends(get_current_user)
) -> dict:
    # Validate user_code
    device_data = await find_device_code_by_user_code(request.user_code)

    # Associate with authenticated user
    await redis.set(
        f"device_approval:{device_data['device_code']}",
        json.dumps({"tenant_id": user.tenant_id, "device_id": user.device_id})
    )

    return {"status": "approved"}

@router.post("/oauth/token")
async def token_endpoint(request: TokenRequest) -> TokenResponse:
    if request.grant_type == "urn:ietf:params:oauth:grant-type:device_code":
        # Check if approved
        approval = await redis.get(f"device_approval:{request.device_code}")
        if not approval:
            raise HTTPException(400, "authorization_pending")

        # Issue tokens
        tokens = issue_tokens(approval["tenant_id"], approval["device_id"])
        return tokens
```

### 3. Token Management

**JWT Access Token (ES256):**
```python
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
import jwt

# Load ES256 private key
with open("private_key.pem", "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

def issue_access_token(tenant_id: str, device_id: str, email: str) -> str:
    payload = {
        "sub": tenant_id,
        "email": email,
        "tenant": tenant_id,
        "device": device_id,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600,  # 1 hour
    }
    return jwt.encode(payload, private_key, algorithm="ES256")

def verify_access_token(token: str) -> dict:
    with open("public_key.pem", "rb") as f:
        public_key = serialization.load_pem_public_key(f.read())

    return jwt.decode(token, public_key, algorithms=["ES256"])
```

**Refresh Token (Opaque):**
```python
import secrets

def issue_refresh_token(tenant_id: str, device_id: str) -> str:
    token = secrets.token_urlsafe(32)

    # Store in database
    await db.execute(
        """
        INSERT INTO refresh_tokens (token, tenant_id, device_id, expires_at)
        VALUES ($1, $2, $3, NOW() + INTERVAL '30 days')
        """,
        token, tenant_id, device_id
    )

    return token

async def refresh_access_token(refresh_token: str) -> TokenResponse:
    # Validate refresh token
    record = await db.fetchrow(
        "SELECT tenant_id, device_id FROM refresh_tokens WHERE token = $1 AND expires_at > NOW()",
        refresh_token
    )

    if not record:
        raise HTTPException(401, "Invalid refresh token")

    # Rotate refresh token (OAuth 2.1 requirement)
    await db.execute("DELETE FROM refresh_tokens WHERE token = $1", refresh_token)

    # Issue new tokens
    new_access_token = issue_access_token(record["tenant_id"], record["device_id"])
    new_refresh_token = await issue_refresh_token(record["tenant_id"], record["device_id"])

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "Bearer",
        "expires_in": 3600
    }
```

### 4. Middleware

```python
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(request: Request) -> User:
    # Extract token from Authorization header
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "Missing authorization")

    token = auth[7:]  # Remove "Bearer "

    # Verify JWT
    try:
        payload = verify_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")

    # Return user context
    return User(
        id=payload["sub"],
        email=payload["email"],
        tenant_id=payload["tenant"],
        device_id=payload["device"]
    )

# Use as dependency
@router.get("/api/v1/resources")
async def list_resources(user: User = Depends(get_current_user)):
    # user.tenant_id automatically scopes query
    resources = await memory_engine.search_resources(tenant_id=user.tenant_id)
    return resources
```

## Security Considerations

### PKCE (Proof Key for Code Exchange)

Required for all public clients (mobile, desktop):

```python
@router.post("/oauth/authorize")
async def authorize(request: AuthorizationRequest):
    # Validate PKCE
    if not request.code_challenge or request.code_challenge_method != "S256":
        raise HTTPException(400, "PKCE required")

    # Store code_challenge
    auth_code = generate_auth_code()
    await redis.setex(
        f"auth_code:{auth_code}",
        300,
        json.dumps({"code_challenge": request.code_challenge})
    )

    return {"code": auth_code}

@router.post("/oauth/token")
async def token_exchange(request: TokenRequest):
    # Verify code_verifier
    auth_data = await redis.get(f"auth_code:{request.code}")

    expected_challenge = base64url(sha256(request.code_verifier))
    if expected_challenge != auth_data["code_challenge"]:
        raise HTTPException(400, "Invalid code_verifier")

    # Issue tokens
    ...
```

### Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/auth/register")
@limiter.limit("5/minute")
async def register_device(...):
    ...

@router.post("/oauth/token")
@limiter.limit("10/minute")
async def token_endpoint(...):
    ...
```

### Audit Logging

```python
@router.post("/auth/verify")
async def verify_device(request: DeviceVerificationRequest):
    try:
        # ... verification logic ...
        await audit_log("device_verified", tenant_id=tenant.id, device_id=device.id)
        return tokens
    except Exception as e:
        await audit_log("device_verification_failed", error=str(e), ip=request.client.host)
        raise
```

## Encryption Key Management Models

Percolate supports two security models for managing tenant encryption keys, balancing ease of development with production security requirements.

### Model 1: Node-Based Keys (Medium-Secure)

**Use Case:** Development, testing, self-hosted single-user deployments

**Key Storage:** Each node stores the tenant's encryption keypair

```
┌─────────────────────────────────────────┐
│ Tenant Data (encrypted at rest)        │
│  - RocksDB encrypted with node key     │
│  - Context blobs encrypted with node key│
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Node A (Desktop)                        │
│  ┌────────────────────────────────────┐ │
│  │ Tenant Keypair (Ed25519 + X25519) │ │
│  │  - Stored in node's secure storage│ │
│  │  - Encrypted with node master key │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Node B (Cloud Pod)                      │
│  ┌────────────────────────────────────┐ │
│  │ Same Tenant Keypair (synced)      │ │
│  │  - Synced via secure channel      │ │
│  │  - Node-level encryption          │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Implementation:**

```python
# percolate/src/percolate/crypto/node_keys.py

class NodeKeyManager:
    """Manages tenant keypairs at the node level"""

    def __init__(self, node_master_key: bytes):
        """Initialize with node-level master key"""
        self.master_key = node_master_key

    async def get_or_create_tenant_keypair(
        self,
        tenant_id: str
    ) -> TenantKeypair:
        """Get existing or create new keypair for tenant"""

        # Check if keypair exists
        encrypted_keypair = await self.db.get(f"tenant_keys:{tenant_id}")

        if encrypted_keypair:
            # Decrypt with node master key
            keypair_data = decrypt_with_chacha20(
                encrypted_keypair,
                self.master_key
            )
            return TenantKeypair.from_bytes(keypair_data)

        # Create new keypair
        signing_key = Ed25519PrivateKey.generate()
        encryption_key = X25519PrivateKey.generate()

        keypair = TenantKeypair(
            signing_private=signing_key,
            signing_public=signing_key.public_key(),
            encryption_private=encryption_key,
            encryption_public=encryption_key.public_key()
        )

        # Encrypt and store
        encrypted = encrypt_with_chacha20(
            keypair.to_bytes(),
            self.master_key
        )
        await self.db.put(f"tenant_keys:{tenant_id}", encrypted)

        return keypair

    async def encrypt_data(
        self,
        tenant_id: str,
        data: bytes
    ) -> bytes:
        """Encrypt data with tenant's public key"""
        keypair = await self.get_or_create_tenant_keypair(tenant_id)
        return encrypt_x25519(data, keypair.encryption_public)

    async def decrypt_data(
        self,
        tenant_id: str,
        encrypted_data: bytes
    ) -> bytes:
        """Decrypt data with tenant's private key"""
        keypair = await self.get_or_create_tenant_keypair(tenant_id)
        return decrypt_x25519(encrypted_data, keypair.encryption_private)
```

**Key Sync Between Nodes:**

```python
class NodeKeySync:
    """Sync tenant keys between user's nodes"""

    async def sync_keys_to_new_node(
        self,
        tenant_id: str,
        from_node: str,
        to_node: str,
        auth_token: str  # User must authorize
    ):
        """
        Transfer encrypted tenant keypair to a new node
        Only works if user authorizes from authenticated session
        """

        # Verify user authorization
        user = await verify_access_token(auth_token)
        if user.tenant_id != tenant_id:
            raise UnauthorizedException()

        # Get keypair from source node
        keypair = await from_node.get_tenant_keypair(tenant_id)

        # Encrypt for transit (using from_node's master key)
        transit_key = generate_ephemeral_x25519_key()
        encrypted_keypair = encrypt_x25519(
            keypair.to_bytes(),
            transit_key.public_key()
        )

        # Send to destination node
        await to_node.receive_tenant_keypair(
            tenant_id,
            encrypted_keypair,
            transit_key.private_key()
        )
```

**Benefits:**
- Simple: Nodes can encrypt/decrypt autonomously
- Fast: No mobile device interaction needed
- Development-friendly: Easy to test locally
- Each node still encrypted separately

**Security Trade-offs:**
- Keypairs exist on servers (potential attack surface)
- Node compromise exposes tenant keys
- Not suitable for highly sensitive data

**Recommended For:**
- Development and testing
- Self-hosted single-user deployments
- Low-sensitivity use cases
- Internal/enterprise deployments with trusted infrastructure

---

### Model 2: Mobile-Only Keys (Fully-Secure)

**Use Case:** Production multi-tenant SaaS, high-security deployments

**Key Storage:** ONLY on mobile device in secure enclave

```
┌─────────────────────────────────────────┐
│ Mobile Device (Secure Enclave)         │
│  ┌────────────────────────────────────┐ │
│  │ Tenant Keypair (NEVER leaves)     │ │
│  │  - Ed25519 signing key            │ │
│  │  - X25519 encryption key          │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
           │ (signs/encrypts on device)
           ▼
┌─────────────────────────────────────────┐
│ Node A (Cloud Pod)                      │
│  - Stores tenant PUBLIC keys only      │
│  - Encrypted data (can't decrypt)      │
│  - Sends decrypt requests to mobile    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ Node B (Desktop)                        │
│  - Stores tenant PUBLIC keys only      │
│  - Must request operations from mobile │
└─────────────────────────────────────────┘
```

**Implementation:**

```python
# percolate/src/percolate/crypto/mobile_keys.py

class MobileKeyManager:
    """Manages keys stored ONLY on mobile device"""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        # Nodes only store public keys
        self.signing_public_key: Optional[bytes] = None
        self.encryption_public_key: Optional[bytes] = None

    async def register_mobile_device(
        self,
        signing_public_key: bytes,
        encryption_public_key: bytes
    ):
        """Store public keys when mobile device registers"""
        self.signing_public_key = signing_public_key
        self.encryption_public_key = encryption_public_key

        # Store in database (public keys only)
        await self.db.put(
            f"tenant_public_keys:{self.tenant_id}",
            json.dumps({
                "signing": base64.b64encode(signing_public_key),
                "encryption": base64.b64encode(encryption_public_key)
            })
        )

    async def encrypt_data(self, data: bytes) -> bytes:
        """
        Encrypt data with tenant's public key
        Only mobile device can decrypt
        """
        if not self.encryption_public_key:
            raise ValueError("Mobile device not registered")

        return encrypt_x25519(data, self.encryption_public_key)

    async def request_decryption(
        self,
        encrypted_data: bytes,
        context: str
    ) -> bytes:
        """
        Request mobile device to decrypt data
        User must approve on mobile device
        """

        # Create decryption request
        request_id = uuid4()
        await self.db.put(
            f"decrypt_request:{request_id}",
            json.dumps({
                "tenant_id": self.tenant_id,
                "encrypted_data": base64.b64encode(encrypted_data),
                "context": context,
                "timestamp": time.time()
            })
        )

        # Send push notification to mobile device
        await send_push_notification(
            self.tenant_id,
            {
                "type": "decrypt_request",
                "request_id": str(request_id),
                "context": context
            }
        )

        # Wait for mobile to respond (with timeout)
        decrypted_data = await self.wait_for_decryption_response(
            request_id,
            timeout=30  # 30 seconds
        )

        return decrypted_data

    async def wait_for_decryption_response(
        self,
        request_id: str,
        timeout: int
    ) -> bytes:
        """Poll for mobile device response"""
        start = time.time()
        while time.time() - start < timeout:
            response = await self.db.get(f"decrypt_response:{request_id}")
            if response:
                return base64.b64decode(response["decrypted_data"])
            await asyncio.sleep(0.5)

        raise TimeoutError("Mobile device did not respond")
```

**Mobile Device Decryption Endpoint:**

```python
# Mobile app makes authenticated request to server endpoint

@router.post("/api/v1/crypto/decrypt")
async def handle_decrypt_request(
    request: DecryptRequest,
    user: User = Depends(get_current_user)
):
    """
    Mobile device fetches pending decrypt requests,
    decrypts on-device, and returns result
    """

    # Get pending request
    decrypt_request = await db.get(f"decrypt_request:{request.request_id}")

    if decrypt_request["tenant_id"] != user.tenant_id:
        raise HTTPException(403, "Unauthorized")

    # Mobile decrypts locally and sends back result
    # (decryption happens on mobile device, not server)

    # Store response
    await db.put(
        f"decrypt_response:{request.request_id}",
        json.dumps({
            "decrypted_data": request.decrypted_data  # Already decrypted on mobile
        })
    )

    return {"status": "completed"}
```

**Context Blob Encryption (Mobile-Only Mode):**

```python
class SecureContextBlobManager:
    """Context blobs in mobile-only security model"""

    async def store_context_blob(
        self,
        tenant_id: str,
        context: ContextBlob
    ):
        """
        Encrypt context blob with tenant's public key
        Only mobile device can decrypt
        """

        # Serialize context
        context_data = json.dumps(context.dict()).encode()

        # Encrypt with tenant's public key (node has this)
        key_manager = MobileKeyManager(tenant_id)
        encrypted_blob = await key_manager.encrypt_data(context_data)

        # Store in S3
        await s3.put_object(
            Bucket="percolate-context-cache",
            Key=f"tenants/{tenant_id}/context.bin",
            Body=encrypted_blob
        )

    async def use_context_blob_for_response(
        self,
        tenant_id: str,
        message: str
    ):
        """
        Use cached context for instant response
        Requires mobile device to decrypt first
        """

        # Fetch encrypted blob from S3
        encrypted_blob = await s3.get_object(
            Bucket="percolate-context-cache",
            Key=f"tenants/{tenant_id}/context.bin"
        )

        # Request decryption from mobile device
        key_manager = MobileKeyManager(tenant_id)
        decrypted_data = await key_manager.request_decryption(
            encrypted_blob,
            context="Using cached context for instant response"
        )

        # Parse decrypted context
        context = ContextBlob(**json.loads(decrypted_data))

        # Generate response using context
        return await self.generate_from_context(context, message)
```

**Benefits:**
- Maximum security: Private keys never leave mobile device
- Zero-trust: Nodes can't decrypt even if compromised
- User control: Explicit approval for sensitive operations
- Compliance-friendly: Meets strictest data protection requirements

**Security Trade-offs:**
- Complexity: Requires push notifications and mobile interaction
- Latency: Decrypt operations wait for mobile device response
- Availability: User must have mobile device accessible
- Development friction: Harder to test without mobile device

**Recommended For:**
- Production multi-tenant SaaS
- Healthcare, financial, or other regulated industries
- High-security use cases
- Privacy-focused applications

---

### Choosing a Security Model

**Decision Matrix:**

| Factor | Node-Based (Medium) | Mobile-Only (Fully-Secure) |
|--------|---------------------|----------------------------|
| **Security Level** | Medium | Maximum |
| **Development Speed** | Fast | Slow |
| **Testing Complexity** | Low | High |
| **User Experience** | Seamless | Requires mobile approvals |
| **Infrastructure** | Simple | Complex (push, websockets) |
| **Compliance** | Basic | Advanced (HIPAA, GDPR++) |
| **Cold Start Latency** | <500ms | 2-5s (mobile decrypt) |

**Recommendation:**

```python
# percolate/src/percolate/settings.py

class SecuritySettings(BaseSettings):
    """Security model configuration"""

    # Security model selection
    key_management_mode: str = "node_based"  # node_based | mobile_only

    # Node-based settings
    node_master_key: Optional[str] = None  # For encrypting tenant keys

    # Mobile-only settings
    enable_push_notifications: bool = False
    decrypt_request_timeout: int = 30  # seconds

    class Config:
        env_prefix = "PERCOLATE_SECURITY_"

# Usage in code
if settings.security.key_management_mode == "node_based":
    key_manager = NodeKeyManager(settings.security.node_master_key)
else:
    key_manager = MobileKeyManager(tenant_id)
```

**Migration Path:**

1. **Phase 1 (MVP)**: Use node-based for development
2. **Phase 2 (Beta)**: Test mobile-only with select users
3. **Phase 3 (Production)**: Offer both as tier options
   - Free/Standard tiers: Node-based (acceptable security)
   - Premium tier: Mobile-only (maximum security)
4. **Phase 4 (Enterprise)**: Mobile-only mandatory for all

**Hybrid Approach (Advanced):**

Allow per-tenant configuration:

```python
class TenantConfig:
    security_mode: str  # "node_based" | "mobile_only"

# Tier A (Premium) defaults to mobile-only
if tenant.tier == TenantTier.A:
    tenant.config.security_mode = "mobile_only"
else:
    tenant.config.security_mode = "node_based"
```

## Testing

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_device_registration_flow():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Register device
        response = await client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "public_key": "...",
            "device_name": "Test Device"
        })
        assert response.status_code == 200
        verification_code_id = response.json()["verification_code_id"]

        # Verify (mock signature)
        response = await client.post("/api/v1/auth/verify", json={
            "verification_code_id": verification_code_id,
            "verification_code": "123456",  # From test email
            "signature": "..."
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_node_based_encryption():
    """Test node-based key management"""
    key_manager = NodeKeyManager(node_master_key=b"test_key" * 4)

    # Encrypt data for tenant
    encrypted = await key_manager.encrypt_data("tenant-123", b"secret data")

    # Decrypt on same node
    decrypted = await key_manager.decrypt_data("tenant-123", encrypted)
    assert decrypted == b"secret data"

@pytest.mark.asyncio
async def test_mobile_only_encryption():
    """Test mobile-only key management"""
    key_manager = MobileKeyManager("tenant-123")

    # Register mobile public keys
    signing_key = Ed25519PrivateKey.generate()
    encryption_key = X25519PrivateKey.generate()

    await key_manager.register_mobile_device(
        signing_public_key=signing_key.public_key().public_bytes(),
        encryption_public_key=encryption_key.public_key().public_bytes()
    )

    # Encrypt data (node can do this with public key)
    encrypted = await key_manager.encrypt_data(b"secret data")

    # Decrypt requires mobile device
    # (in test, mock the mobile response)
    with mock.patch.object(key_manager, 'wait_for_decryption_response') as mock_decrypt:
        mock_decrypt.return_value = b"secret data"
        decrypted = await key_manager.request_decryption(encrypted, "test")
        assert decrypted == b"secret data"
```
