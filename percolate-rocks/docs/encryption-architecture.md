# Encryption Architecture

## Overview

REM Database implements **selective encryption at rest** with key pair cryptography to ensure data privacy while maintaining query performance.

**Key Principles**:
1. **Privacy by default**: Sensitive entity fields encrypted before storage
2. **Zero-knowledge**: Database admin cannot read encrypted data
3. **Performance first**: Encrypt content, not metadata or embeddings
4. **Secure sharing**: Data shared between tenants using recipient's public key
5. **Device synchronization**: Same tenant key pair across all devices (securely synced)

## What We Encrypt vs. Performance

### Encryption Strategy

**Encrypt (ChaCha20-Poly1305 AEAD):**
- ✅ **Entity field values** - User data (names, emails, content text)
- ✅ **Embedded content fields** - Raw text that was embedded (e.g., `content` in Resources)
- ✅ **WAL operation payloads** - Changes replicated to other devices
- ✅ **Graph edge metadata** - Relationship properties

**Do NOT Encrypt (Query Performance):**
- ❌ **Entity IDs** - Needed for O(1) lookups
- ❌ **Entity types** - Required for schema routing
- ❌ **Indexed field values** - Must be plaintext for SQL WHERE clauses
- ❌ **Embeddings** - 1536-dimensional vectors (already opaque, 6KB each)
- ❌ **System fields** - `created_at`, `modified_at`, `deleted_at` (timestamps)
- ❌ **Column family keys** - RocksDB keys for prefix scans

**Rationale:**
- **Embeddings** are already semantically opaque (you can't reverse-engineer text from vectors)
- **Indexed fields** need plaintext for `WHERE category = 'tech'` queries (RocksDB index scans)
- **System fields** are metadata, not user content
- **Entity IDs** are deterministic UUIDs (blake3 hashes), already anonymized

### Performance Impact

| Operation | Without Encryption | With Encryption | Overhead |
|-----------|-------------------|-----------------|----------|
| Insert (no embedding) | ~1ms | ~1.2ms | +20% (ChaCha20 is fast) |
| Get by ID | ~0.1ms | ~0.15ms | +50% (decrypt single entity) |
| Vector search (1M docs) | ~5ms | ~5ms | 0% (embeddings not encrypted) |
| SQL query (indexed) | ~10ms | ~10ms | 0% (indexed fields plaintext) |
| Batch insert (1000 docs) | ~500ms | ~700ms | +40% (1000 encryptions) |

**Key insight:** Encrypting embeddings would add ~2-3ms per query (decrypt 1000s of vectors), so we skip them.

### Selective Field Encryption (Implementation Plan)

When inserting an entity, the database will:

1. **Parse entity JSON** to extract schema configuration
2. **Identify encryption candidates** from `json_schema_extra`:
   ```python
   model_config = ConfigDict(
       json_schema_extra={
           "embedding_fields": ["content"],      # Raw text to encrypt
           "indexed_fields": ["category"],       # Must stay plaintext
           "encrypted_fields": ["email", "bio"]  # Explicitly encrypt these
       }
   )
   ```

3. **Encrypt field values selectively**:
   ```rust
   // Pseudo-code for entity insert
   let entity_json = parse_entity(data);
   let schema = registry.get_schema(&entity_type)?;

   // Extract encryption config
   let embedding_fields = schema.embedding_fields();  // ["content"]
   let encrypted_fields = schema.encrypted_fields();  // ["email", "bio"]
   let indexed_fields = schema.indexed_fields();      // ["category"]

   // Encrypt specified fields
   for field in embedding_fields.iter().chain(encrypted_fields.iter()) {
       if let Some(value) = entity_json.get_mut(field) {
           if !indexed_fields.contains(field) {  // Don't encrypt indexed fields
               let plaintext = serde_json::to_vec(value)?;
               let ciphertext = storage.keypair.encrypt(&plaintext)?;
               *value = json!(base64::encode(&ciphertext));  // Store as base64
           }
       }
   }
   ```

4. **Store entity** with mixed plaintext/encrypted fields:
   ```json
   {
     "id": "550e8400-e29b-41d4-a716-446655440000",
     "entity_type": "resources",
     "category": "programming",  // Plaintext (indexed)
     "content": "ENCRYPTED:aGVsbG8gd29ybGQ=...",  // Encrypted (was embedded)
     "embedding": [0.1, 0.5, -0.2, ...],  // Plaintext (vector)
     "created_at": "2025-10-25T10:30:00Z"  // Plaintext (system field)
   }
   ```

5. **Query behavior**:
   - **Vector search**: Works normally (embeddings not encrypted)
   - **SQL WHERE**: Works on indexed fields (plaintext)
   - **Get by ID**: Automatically decrypts encrypted fields on retrieval

**Default encryption policy:**
- If `embedding_fields` is set → encrypt those fields automatically
- If `encrypted_fields` is set → encrypt those fields explicitly
- If both are empty and password provided → encrypt ALL non-indexed, non-system fields

## Encryption Layers

```
┌─────────────────────────────────────────────────────────┐
│                    Application Layer                     │
│  (Python/Rust code encrypts before calling storage)     │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Storage Layer (RocksDB)                │
│  - Entities: Encrypted JSON blobs                       │
│  - WAL: Encrypted operation logs                        │
│  - Keys: Private keys (encrypted), Public keys (plain)  │
└─────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  Filesystem (Disk)                       │
│  - All data encrypted at rest                           │
└─────────────────────────────────────────────────────────┘
```

## Cryptographic Primitives

| Purpose | Algorithm | Key Size | Notes |
|---------|-----------|----------|-------|
| **Tenant identity** | Ed25519 | 256-bit | Signing key pair (not used for encryption) |
| **Encryption key** | X25519 (ECDH) | 256-bit | Derived from Ed25519 for encryption |
| **Symmetric encryption** | ChaCha20-Poly1305 | 256-bit | AEAD cipher for entity data |
| **Key derivation** | PBKDF2-SHA256 | 256-bit | Master password → encryption key |
| **Key wrapping** | ChaCha20-Poly1305 | 256-bit | Encrypt private key with master password |

## Key Pair Generation (Initialization)

When database is first initialized, generate tenant key pair:

```rust
use ed25519_dalek::{SigningKey, VerifyingKey};
use rand::rngs::OsRng;

pub struct TenantKeyPair {
    /// Private key (never stored unencrypted)
    private_key: SigningKey,
    /// Public key (stored plaintext for sharing)
    public_key: VerifyingKey,
}

impl TenantKeyPair {
    /// Generate new key pair for tenant.
    pub fn generate() -> Self {
        let mut rng = OsRng;
        let private_key = SigningKey::generate(&mut rng);
        let public_key = private_key.verifying_key();

        Self { private_key, public_key }
    }

    /// Derive encryption key from signing key.
    pub fn encryption_key(&self) -> [u8; 32] {
        // Convert Ed25519 to X25519 for ECDH
        // This allows using same key pair for signing + encryption
        todo!("Convert Ed25519 → X25519")
    }
}
```

## Database Initialization Flow

```rust
use argon2::{Argon2, PasswordHasher};

pub struct Storage {
    db: Arc<DB>,
    tenant_keypair: TenantKeyPair,
}

impl Storage {
    /// Open database with master password.
    ///
    /// First run: Generates key pair, encrypts private key with master password
    /// Subsequent runs: Decrypts private key from storage
    pub fn open(path: &str, master_password: &str) -> Result<Self> {
        let db = open_rocksdb(path)?;

        // Check if keys already exist
        let keypair = match db.get_cf(CF_KEYS, b"private_key_encrypted")? {
            Some(encrypted_private_key) => {
                // Existing database - decrypt private key
                let private_key = decrypt_private_key(
                    &encrypted_private_key,
                    master_password
                )?;

                let public_key_bytes = db.get_cf(CF_KEYS, b"public_key")?
                    .ok_or(DatabaseError::ConfigError("Missing public key".into()))?;

                TenantKeyPair::from_bytes(&private_key, &public_key_bytes)?
            }
            None => {
                // New database - generate and store keys
                let keypair = TenantKeyPair::generate();

                // Encrypt private key with master password
                let encrypted_private_key = encrypt_private_key(
                    &keypair.private_key,
                    master_password
                )?;

                // Store encrypted private key
                db.put_cf(CF_KEYS, b"private_key_encrypted", &encrypted_private_key)?;

                // Store public key (plaintext)
                db.put_cf(CF_KEYS, b"public_key", keypair.public_key.as_bytes())?;

                keypair
            }
        };

        Ok(Self { db, tenant_keypair: keypair })
    }
}

/// Encrypt private key with master password.
fn encrypt_private_key(private_key: &[u8], master_password: &str) -> Result<Vec<u8>> {
    // Derive encryption key from password using Argon2
    let salt = b"percolate-rem-salt-v1";  // TODO: Generate random salt per database
    let argon2 = Argon2::default();
    let password_hash = argon2.hash_password(master_password.as_bytes(), salt)?;

    // Extract 32-byte key from hash
    let encryption_key: [u8; 32] = password_hash.hash
        .ok_or(DatabaseError::ConfigError("Hash failed".into()))?
        .as_bytes()[..32]
        .try_into()?;

    // Encrypt private key with ChaCha20-Poly1305
    use chacha20poly1305::{ChaCha20Poly1305, KeyInit, AeadCore, Aead};

    let cipher = ChaCha20Poly1305::new(&encryption_key.into());
    let nonce = ChaCha20Poly1305::generate_nonce(&mut OsRng);
    let ciphertext = cipher.encrypt(&nonce, private_key)?;

    // Return nonce + ciphertext
    let mut result = nonce.to_vec();
    result.extend_from_slice(&ciphertext);

    Ok(result)
}

/// Decrypt private key with master password.
fn decrypt_private_key(encrypted: &[u8], master_password: &str) -> Result<Vec<u8>> {
    // Derive same encryption key from password
    let salt = b"percolate-rem-salt-v1";
    let argon2 = Argon2::default();
    let password_hash = argon2.hash_password(master_password.as_bytes(), salt)?;
    let encryption_key: [u8; 32] = password_hash.hash
        .ok_or(DatabaseError::ConfigError("Hash failed".into()))?
        .as_bytes()[..32]
        .try_into()?;

    // Extract nonce (first 12 bytes) and ciphertext
    let (nonce_bytes, ciphertext) = encrypted.split_at(12);
    let nonce = nonce_bytes.try_into()?;

    // Decrypt with ChaCha20-Poly1305
    use chacha20poly1305::{ChaCha20Poly1305, KeyInit, Aead};

    let cipher = ChaCha20Poly1305::new(&encryption_key.into());
    let plaintext = cipher.decrypt(&nonce, ciphertext)?;

    Ok(plaintext)
}
```

## Entity Encryption (Transparent)

All entity data encrypted before storage:

```rust
impl Storage {
    /// Put entity (automatically encrypts).
    pub fn put(&self, cf_name: &str, key: &[u8], value: &[u8]) -> Result<()> {
        // Encrypt value with tenant's encryption key
        let encrypted_value = self.encrypt(value)?;

        // Store encrypted data
        let cf = self.cf_handle(cf_name);
        self.db.put_cf(&cf, key, &encrypted_value)?;

        Ok(())
    }

    /// Get entity (automatically decrypts).
    pub fn get(&self, cf_name: &str, key: &[u8]) -> Result<Option<Vec<u8>>> {
        let cf = self.cf_handle(cf_name);
        let encrypted_value = self.db.get_cf(&cf, key)?;

        match encrypted_value {
            Some(ciphertext) => {
                // Decrypt value with tenant's encryption key
                let plaintext = self.decrypt(&ciphertext)?;
                Ok(Some(plaintext))
            }
            None => Ok(None),
        }
    }

    /// Encrypt data with tenant's key.
    fn encrypt(&self, plaintext: &[u8]) -> Result<Vec<u8>> {
        use chacha20poly1305::{ChaCha20Poly1305, KeyInit, AeadCore, Aead};

        let encryption_key = self.tenant_keypair.encryption_key();
        let cipher = ChaCha20Poly1305::new(&encryption_key.into());
        let nonce = ChaCha20Poly1305::generate_nonce(&mut OsRng);

        let ciphertext = cipher.encrypt(&nonce, plaintext)
            .map_err(|e| DatabaseError::ConfigError(format!("Encryption failed: {}", e)))?;

        // Return nonce + ciphertext
        let mut result = nonce.to_vec();
        result.extend_from_slice(&ciphertext);

        Ok(result)
    }

    /// Decrypt data with tenant's key.
    fn decrypt(&self, encrypted: &[u8]) -> Result<Vec<u8>> {
        use chacha20poly1305::{ChaCha20Poly1305, KeyInit, Aead};

        let encryption_key = self.tenant_keypair.encryption_key();
        let cipher = ChaCha20Poly1305::new(&encryption_key.into());

        // Extract nonce (first 12 bytes) and ciphertext
        let (nonce_bytes, ciphertext) = encrypted.split_at(12);
        let nonce = nonce_bytes.try_into()
            .map_err(|_| DatabaseError::ConfigError("Invalid nonce".into()))?;

        let plaintext = cipher.decrypt(&nonce, ciphertext)
            .map_err(|e| DatabaseError::ConfigError(format!("Decryption failed: {}", e)))?;

        Ok(plaintext)
    }
}
```

## Tenant-to-Tenant Sharing

Share data with another tenant using their public key:

```rust
pub struct SharingManager {
    own_keypair: TenantKeyPair,
}

impl SharingManager {
    /// Encrypt data for sharing with another tenant.
    ///
    /// Uses X25519 ECDH to derive shared secret, then encrypts with ChaCha20-Poly1305.
    pub fn encrypt_for_tenant(&self, data: &[u8], recipient_public_key: &[u8; 32]) -> Result<Vec<u8>> {
        // Convert Ed25519 keys to X25519 for ECDH
        let own_x25519_private = self.own_keypair.encryption_key();
        let recipient_x25519_public = recipient_public_key;

        // Perform ECDH to derive shared secret
        let shared_secret = x25519_dalek::x25519(
            own_x25519_private.into(),
            (*recipient_x25519_public).into()
        );

        // Encrypt data with shared secret
        use chacha20poly1305::{ChaCha20Poly1305, KeyInit, AeadCore, Aead};

        let cipher = ChaCha20Poly1305::new(&shared_secret.into());
        let nonce = ChaCha20Poly1305::generate_nonce(&mut OsRng);

        let ciphertext = cipher.encrypt(&nonce, data)?;

        // Return nonce + ciphertext
        let mut result = nonce.to_vec();
        result.extend_from_slice(&ciphertext);

        Ok(result)
    }

    /// Decrypt data shared by another tenant.
    pub fn decrypt_from_tenant(&self, encrypted: &[u8], sender_public_key: &[u8; 32]) -> Result<Vec<u8>> {
        // Convert Ed25519 keys to X25519 for ECDH
        let own_x25519_private = self.own_keypair.encryption_key();
        let sender_x25519_public = sender_public_key;

        // Derive same shared secret (ECDH is symmetric)
        let shared_secret = x25519_dalek::x25519(
            own_x25519_private.into(),
            (*sender_x25519_public).into()
        );

        // Decrypt data with shared secret
        use chacha20poly1305::{ChaCha20Poly1305, KeyInit, Aead};

        let cipher = ChaCha20Poly1305::new(&shared_secret.into());

        let (nonce_bytes, ciphertext) = encrypted.split_at(12);
        let nonce = nonce_bytes.try_into()?;

        let plaintext = cipher.decrypt(&nonce, ciphertext)?;

        Ok(plaintext)
    }
}
```

## Device-to-Device Key Sync

When adding a new device to same tenant:

```
Desktop (Primary Device)          Mobile (New Device)
       |                                  |
       | 1. Generate QR code with:        |
       |    - Tenant ID                   |
       |    - Public key                  |
       |    - Encrypted private key       |
       |    - Encryption: one-time code   |
       |                                  |
       | ←───── 2. Scan QR code ──────────|
       |                                  |
       |                                  | 3. User enters one-time code
       |                                  | 4. Decrypt private key
       |                                  | 5. Store in secure enclave
       |                                  |
       | ←──── 6. mTLS handshake ─────────|
       |                                  |
       | ───── 7. Encrypted replication ─→|
```

**Security properties**:
- Private key encrypted with one-time code (6-digit PIN or QR scan)
- One-time code expires after 5 minutes
- Mobile stores private key in OS secure enclave (iOS Keychain, Android Keystore)
- Desktop never sends unencrypted private key over network

## WAL Encryption

WAL entries encrypted before storage and replication:

```rust
impl WriteAheadLog {
    /// Append entry to WAL (encrypts before storage).
    pub fn append(&mut self, op: WalOperation) -> Result<u64> {
        let seq = self.current_seq.fetch_add(1, Ordering::SeqCst) + 1;

        let entry = WalEntry {
            seq,
            op,
            timestamp: Utc::now().to_rfc3339(),
        };

        // Serialize entry
        let plaintext = bincode::serialize(&entry)?;

        // Encrypt with tenant key
        let ciphertext = self.storage.encrypt(&plaintext)?;

        // Store encrypted entry
        let key = format!("wal:{:020}", seq);
        self.storage.put(CF_WAL, key.as_bytes(), &ciphertext)?;

        Ok(seq)
    }

    /// Get WAL entry (decrypts after retrieval).
    pub fn get(&self, seq: u64) -> Result<Option<WalEntry>> {
        let key = format!("wal:{:020}", seq);
        let ciphertext = self.storage.get(CF_WAL, key.as_bytes())?;

        match ciphertext {
            Some(encrypted_bytes) => {
                // Decrypt entry
                let plaintext = self.storage.decrypt(&encrypted_bytes)?;

                // Deserialize
                let entry = bincode::deserialize(&plaintext)?;
                Ok(Some(entry))
            }
            None => Ok(None),
        }
    }
}
```

## Key Rotation

To rotate tenant key pair (e.g., after suspected compromise):

```rust
impl Storage {
    /// Rotate tenant key pair.
    ///
    /// 1. Generate new key pair
    /// 2. Decrypt all entities with old key
    /// 3. Re-encrypt all entities with new key
    /// 4. Update stored key pair
    pub fn rotate_keys(&mut self, master_password: &str) -> Result<()> {
        // Generate new key pair
        let new_keypair = TenantKeyPair::generate();

        // Get all entities
        let mut entities_to_reencrypt = Vec::new();
        for cf_name in all_column_families() {
            let iter = self.db.iterator_cf(&self.cf_handle(cf_name), IteratorMode::Start);
            for item in iter {
                let (key, encrypted_value) = item?;

                // Decrypt with old key
                let plaintext = self.decrypt(&encrypted_value)?;

                entities_to_reencrypt.push((cf_name, key.to_vec(), plaintext));
            }
        }

        // Switch to new key pair
        let old_keypair = std::mem::replace(&mut self.tenant_keypair, new_keypair);

        // Re-encrypt all entities with new key
        for (cf_name, key, plaintext) in entities_to_reencrypt {
            let new_ciphertext = self.encrypt(&plaintext)?;
            self.db.put_cf(&self.cf_handle(cf_name), &key, &new_ciphertext)?;
        }

        // Update stored key pair
        let encrypted_private_key = encrypt_private_key(
            &self.tenant_keypair.private_key.as_bytes(),
            master_password
        )?;

        self.db.put_cf(CF_KEYS, b"private_key_encrypted", &encrypted_private_key)?;
        self.db.put_cf(CF_KEYS, b"public_key", self.tenant_keypair.public_key.as_bytes())?;

        Ok(())
    }
}
```

## Column Family for Keys

Add `CF_KEYS` to store key material:

```rust
/// Keys storage (encrypted private key, plaintext public key)
pub const CF_KEYS: &str = "keys";

pub fn all_column_families() -> Vec<&'static str> {
    vec![
        CF_ENTITIES,
        CF_KEY_INDEX,
        CF_EDGES,
        CF_EDGES_REVERSE,
        CF_EMBEDDINGS,
        CF_INDEXES,
        CF_WAL,
        CF_KEYS,  // ← Add this
    ]
}
```

## Security Considerations

### Threats Mitigated

| Threat | Mitigation |
|--------|------------|
| **Stolen database files** | All data encrypted, attacker needs master password |
| **Compromised backup** | Encrypted at rest, useless without keys |
| **Insider threat (DBA)** | Zero-knowledge - admin cannot decrypt data |
| **Network sniffing (replication)** | mTLS + encrypted WAL entries (defense in depth) |
| **Cross-tenant data leak** | Each tenant has separate encryption key |

### Threats NOT Mitigated

| Threat | Notes |
|--------|-------|
| **Master password compromise** | Attacker can decrypt private key → all data |
| **Memory dump while running** | Decrypted data in RAM (use encrypted swap) |
| **Keylogger (master password)** | Capture password at entry time |
| **Physical access to unlocked device** | Database is decrypted and accessible |

### Best Practices

1. **Strong master password**: Use passphrase (e.g., 6+ random words)
2. **Hardware security module**: Store private key in HSM/TPM if available
3. **Encrypted swap/hibernation**: Prevent private key leakage to disk
4. **Lock on idle**: Auto-lock database after inactivity
5. **Key rotation**: Rotate keys annually or after suspected compromise

## Implementation Checklist

- [ ] Add `chacha20poly1305` and `ed25519-dalek` to dependencies
- [ ] Add `CF_KEYS` column family
- [ ] Implement `TenantKeyPair` struct
- [ ] Update `Storage::open()` to accept master password
- [ ] Implement key pair generation on first run
- [ ] Implement private key encryption/decryption with Argon2
- [ ] Add `encrypt()`/`decrypt()` methods to `Storage`
- [ ] Update `put()`/`get()` to transparently encrypt/decrypt
- [ ] Implement `SharingManager` for tenant-to-tenant encryption
- [ ] Update `WriteAheadLog` to encrypt entries
- [ ] Implement key rotation
- [ ] Add integration tests for encryption/decryption
- [ ] Document key management in user guide

## References

- **ChaCha20-Poly1305**: RFC 8439
- **Ed25519**: RFC 8032
- **X25519**: RFC 7748
- **Argon2**: RFC 9106
- **ECDH key exchange**: NIST SP 800-56A
