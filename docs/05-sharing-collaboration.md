# Sharing and Collaboration Model

## Overview

Percolate supports **selective data sharing** between users and teams while maintaining privacy-first principles:
- **Resource-level sharing**: Share specific documents, entities, or moments
- **Team workspaces**: Shared memory spaces for collaboration
- **Permission model**: Fine-grained access control (read, write, admin)
- **Encrypted sharing**: End-to-end encryption with key exchange
- **Audit trail**: Complete history of sharing actions

## Sharing Levels

### 1. Private (Default)

All data is private by default:
- Stored in per-tenant RocksDB
- Only accessible to tenant
- No sharing metadata

### 2. Shared with Users

Share specific resources/entities with individuals:
- Explicit permission grants
- Recipient receives encrypted copy
- Original owner maintains control

### 3. Team Workspaces

Collaborative spaces with shared memory:
- Dedicated RocksDB for team
- All team members have access
- Team-level agent-lets

### 4. Public (Optional)

Publicly accessible content:
- Agent-lets in marketplace
- Published documents
- Shared knowledge bases

## Permission Model

### Resource Permissions

```rust
pub enum Permission {
    Read,     // View content
    Write,    // Modify content
    Share,    // Share with others
    Admin,    // Full control (delete, change permissions)
}

pub struct ShareGrant {
    pub resource_id: ResourceId,
    pub grantor: UserId,
    pub grantee: UserId,
    pub permissions: Vec<Permission>,
    pub granted_at: Timestamp,
    pub expires_at: Option<Timestamp>,
}
```

### Permission Inheritance

```
Team Workspace
  ├── Member (Read + Write)
  │   └── Can read all team resources
  ├── Admin (Read + Write + Share + Admin)
  │   └── Can manage team and permissions
  └── Guest (Read only)
      └── Limited access to specific resources
```

## Sharing Flow

### 1. Direct User Sharing

**Flow:**
```
Alice wants to share resource with Bob
  ↓
Alice clicks "Share" on resource
  ↓
Alice enters Bob's email
  ↓
System encrypts resource with shared key
  ↓
System creates share grant
  ↓
Bob receives notification
  ↓
Bob fetches shared resource
  ↓
Resource appears in Bob's shared section
```

**Implementation:**
```python
# API endpoint
@router.post("/api/v1/resources/{resource_id}/share")
async def share_resource(
    resource_id: str,
    request: ShareRequest,
    user: User = Depends(get_current_user)
):
    # Validate resource ownership
    resource = await memory.get_resource(resource_id)
    if resource.tenant_id != user.tenant_id:
        raise HTTPException(403, "Not authorized")

    # Find recipient
    recipient = await get_user_by_email(request.recipient_email)

    # Create share grant
    grant = ShareGrant(
        resource_id=resource_id,
        grantor=user.id,
        grantee=recipient.id,
        permissions=request.permissions,
        granted_at=datetime.now()
    )
    await db.execute("INSERT INTO share_grants (...)")

    # Encrypt resource for recipient
    encrypted_resource = encrypt_for_user(resource, recipient.public_key)

    # Replicate to recipient's node
    await replicate_shared_resource(
        resource=encrypted_resource,
        recipient_node=recipient.primary_node
    )

    # Notify recipient
    await send_notification(recipient.email, "Resource shared with you")

    return {"share_id": grant.id}
```

### 2. Team Workspace Sharing

**Flow:**
```
Create team workspace
  ↓
Invite members (email)
  ↓
Members accept invitation
  ↓
Members added to team
  ↓
Create shared RocksDB for team
  ↓
Sync team resources to all member nodes
```

**Implementation:**
```python
# Team model
@dataclass
class Team:
    id: str
    name: str
    created_by: str
    created_at: datetime
    members: list[TeamMember]

@dataclass
class TeamMember:
    user_id: str
    role: str  # "member", "admin", "guest"
    permissions: list[Permission]
    joined_at: datetime

# Create team
@router.post("/api/v1/teams")
async def create_team(
    request: CreateTeamRequest,
    user: User = Depends(get_current_user)
):
    team = Team(
        id=str(uuid4()),
        name=request.name,
        created_by=user.id,
        created_at=datetime.now(),
        members=[
            TeamMember(
                user_id=user.id,
                role="admin",
                permissions=[Permission.Read, Permission.Write, Permission.Share, Permission.Admin],
                joined_at=datetime.now()
            )
        ]
    )

    # Create team RocksDB
    team_db_path = f"/var/lib/percolate/teams/{team.id}"
    team_memory = MemoryEngine(db_path=team_db_path, tenant_id=team.id)

    await db.execute("INSERT INTO teams (...)")

    return {"team_id": team.id}

# Invite member
@router.post("/api/v1/teams/{team_id}/invite")
async def invite_member(
    team_id: str,
    request: InviteMemberRequest,
    user: User = Depends(get_current_user)
):
    # Validate admin permission
    team = await get_team(team_id)
    if not has_permission(user, team, Permission.Admin):
        raise HTTPException(403, "Admin permission required")

    # Create invitation
    invite = TeamInvitation(
        team_id=team_id,
        email=request.email,
        invited_by=user.id,
        role=request.role,
        expires_at=datetime.now() + timedelta(days=7)
    )

    await db.execute("INSERT INTO team_invitations (...)")

    # Send email
    await send_invitation_email(request.email, team, invite)

    return {"invitation_id": invite.id}
```

## Replication Strategy for Shared Data

### Shared Resource Storage

```
User A's Node (Owner)
  └── resources/{resource_id} → full resource

User B's Node (Shared)
  └── shared_resources/{share_id} → encrypted copy
      └── metadata:
          - owner: User A
          - shared_by: User A
          - permissions: [Read]
          - shared_at: timestamp
```

### Team Workspace Storage

```
Team Workspace
  └── team_db/{team_id}/
      ├── resources/         # Team resources
      ├── entities/          # Team entities
      └── moments/           # Team moments

User A's Node
  └── team_subscriptions/{team_id} → pointer to team DB

User B's Node
  └── team_subscriptions/{team_id} → pointer to team DB
```

### Sync Protocol

**Shared Resources (Copy Model):**
1. Owner makes change to resource
2. Owner's node syncs to cloud
3. Cloud replicates to recipients' nodes
4. Recipients receive notification of update

**Team Workspaces (Shared Memory Model):**
1. Any member makes change
2. Change written to team RocksDB
3. Team DB syncs to all member nodes
4. Vector clocks prevent conflicts

## Encryption for Sharing

### Shared Key Exchange

Use **X25519 key exchange** for shared encryption keys:

```rust
use x25519_dalek::{EphemeralSecret, PublicKey};

pub fn create_shared_key(
    sender_private: &[u8],
    recipient_public: &[u8]
) -> Result<[u8; 32]> {
    let sender_secret = EphemeralSecret::from(sender_private);
    let recipient_public = PublicKey::from(recipient_public);

    // Diffie-Hellman key exchange
    let shared_secret = sender_secret.diffie_hellman(&recipient_public);

    // Derive encryption key with HKDF
    let mut key = [0u8; 32];
    hkdf::Hkdf::<sha2::Sha256>::new(None, shared_secret.as_bytes())
        .expand(b"percolate-share-v1", &mut key)?;

    Ok(key)
}
```

### Encrypted Resource Format

```rust
pub struct EncryptedResource {
    pub resource_id: ResourceId,
    pub ciphertext: Vec<u8>,       // ChaCha20-Poly1305 encrypted
    pub nonce: [u8; 12],            // ChaCha20 nonce
    pub ephemeral_public_key: [u8; 32],  // Sender's ephemeral public key
    pub encrypted_at: Timestamp,
}
```

### Decryption on Recipient Side

```python
# Recipient decrypts shared resource
def decrypt_shared_resource(
    encrypted: EncryptedResource,
    recipient_private_key: bytes
) -> Resource:
    # Compute shared key
    shared_key = create_shared_key(
        recipient_private_key,
        encrypted.ephemeral_public_key
    )

    # Decrypt with ChaCha20-Poly1305
    cipher = ChaCha20Poly1305(shared_key)
    plaintext = cipher.decrypt(encrypted.nonce, encrypted.ciphertext, None)

    # Deserialize
    resource = json.loads(plaintext)
    return Resource(**resource)
```

## Team Workspace Architecture

### Team RocksDB

Each team has dedicated RocksDB:

```
/var/lib/percolate/teams/{team_id}/
  └── rocksdb/
      ├── resources/
      ├── entities/
      ├── moments/
      └── metadata/
```

### Member Access

Members access team workspace through their node:

```python
# Access team resource
async def get_team_resource(
    team_id: str,
    resource_id: str,
    user: User = Depends(get_current_user)
):
    # Validate membership
    if not is_team_member(user.id, team_id):
        raise HTTPException(403, "Not a team member")

    # Load team memory
    team_memory = get_team_memory(team_id)

    # Get resource
    resource = await team_memory.get_resource(resource_id)

    return resource
```

### Sync to Member Nodes

Team resources sync to member nodes:

```python
# Sync team workspace to member node
async def sync_team_workspace(team_id: str, member: User):
    # Get team changes since last sync
    team_memory = get_team_memory(team_id)
    delta = team_memory.compute_delta(from_version=member.last_team_sync)

    # Replicate to member's node
    await replicate_delta(
        delta=delta,
        destination=member.primary_node,
        namespace=f"team:{team_id}"
    )

    # Update last sync
    member.last_team_sync = delta.to_version
```

## Access Control Lists (ACLs)

### Resource-Level ACLs

```sql
CREATE TABLE resource_acls (
    resource_id TEXT NOT NULL,
    principal_id TEXT NOT NULL,  -- user_id or team_id
    principal_type TEXT NOT NULL,  -- 'user' or 'team'
    permissions TEXT[] NOT NULL,
    granted_by TEXT NOT NULL,
    granted_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    PRIMARY KEY (resource_id, principal_id)
);

CREATE INDEX idx_acls_principal ON resource_acls(principal_id, principal_type);
```

### Check Permission

```python
async def check_permission(
    user: User,
    resource_id: str,
    permission: Permission
) -> bool:
    # Check direct user permission
    user_acl = await db.fetchrow(
        "SELECT permissions FROM resource_acls WHERE resource_id = $1 AND principal_id = $2",
        resource_id, user.id
    )
    if user_acl and permission in user_acl["permissions"]:
        return True

    # Check team permissions
    user_teams = await get_user_teams(user.id)
    for team in user_teams:
        team_acl = await db.fetchrow(
            "SELECT permissions FROM resource_acls WHERE resource_id = $1 AND principal_id = $2",
            resource_id, team.id
        )
        if team_acl and permission in team_acl["permissions"]:
            return True

    return False
```

## Audit Trail

### Share Events

```sql
CREATE TABLE share_audit_log (
    id UUID PRIMARY KEY,
    event_type TEXT NOT NULL,  -- 'share_created', 'share_revoked', 'permission_changed'
    resource_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    target_id TEXT,
    details JSONB,
    occurred_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_audit_resource ON share_audit_log(resource_id, occurred_at);
CREATE INDEX idx_audit_actor ON share_audit_log(actor_id, occurred_at);
```

### Log Share Events

```python
async def log_share_event(
    event_type: str,
    resource_id: str,
    actor: User,
    details: dict
):
    await db.execute(
        """
        INSERT INTO share_audit_log (id, event_type, resource_id, actor_id, details, occurred_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        """,
        uuid4(), event_type, resource_id, actor.id, json.dumps(details)
    )
```

## UI/UX Patterns

### Share Dialog

```
┌─────────────────────────────────────┐
│ Share Resource                      │
├─────────────────────────────────────┤
│ Share with:                         │
│ ┌─────────────────────────────────┐ │
│ │ bob@example.com                 │ │
│ └─────────────────────────────────┘ │
│                                     │
│ Permissions:                        │
│ ☑ Read                              │
│ ☐ Write                             │
│ ☐ Share with others                 │
│                                     │
│ Expires:                            │
│ ○ Never                             │
│ ○ In 7 days                         │
│ ○ Custom date                       │
│                                     │
│         [Cancel]  [Share]           │
└─────────────────────────────────────┘
```

### Team Workspace Switcher

```
┌─────────────────────────┐
│ Personal  ▼             │
├─────────────────────────┤
│ ● Personal Workspace    │
│   Team Alpha            │
│   Team Beta             │
│   + Create Team         │
└─────────────────────────┘
```

## Future Enhancements

### Phase 1 (Foundation)
- Direct user sharing (resource-level)
- Basic team workspaces
- Encrypted sharing with X25519
- ACLs and audit log

### Phase 2 (Collaboration)
- Real-time collaboration (OT or CRDT)
- Shared agent-lets within teams
- Comment threads on resources
- Version history for shared resources

### Phase 3 (Advanced)
- Federated sharing (cross-instance)
- Public sharing with links
- Agent-let marketplace
- Team analytics dashboard

### Phase 4 (Enterprise)
- Organization hierarchy (teams within orgs)
- RBAC (role-based access control)
- SSO integration
- Compliance reporting (GDPR, etc.)

## Security Considerations

### Revocation

When share is revoked:
1. Delete share grant from database
2. Tombstone resource on recipient's node
3. Recipient loses access immediately
4. Audit log records revocation

### Key Rotation

For team workspaces:
1. Periodically rotate team encryption key
2. Re-encrypt all team resources
3. Distribute new key to members

### Data Residency

For regulated data:
- Team workspace can specify region
- Data stays in specified region
- Cross-region sync disabled

## References

- X25519 Key Exchange: RFC 7748
- ChaCha20-Poly1305: RFC 8439
- Access Control: NIST RBAC model
- CRDT: Shapiro et al. (2011)
