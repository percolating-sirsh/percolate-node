//! Entity storage operations.

use crate::storage::{keys, Storage, CF_ENTITIES};
use crate::types::{DatabaseError, Entity, Result};
use uuid::Uuid;

/// Entity storage layer.
pub struct EntityStore {
    storage: Storage,
}

impl EntityStore {
    /// Create new entity store.
    pub fn new(storage: Storage) -> Self {
        Self { storage }
    }

    /// Insert entity.
    pub fn insert(&self, tenant_id: &str, entity: &Entity) -> Result<()> {
        let key = keys::encode_entity_key(tenant_id, entity.id);
        let value = serde_json::to_vec(entity)?;

        self.storage.put(CF_ENTITIES, &key, &value)?;

        Ok(())
    }

    /// Get entity by ID.
    pub fn get(&self, tenant_id: &str, entity_id: Uuid) -> Result<Option<Entity>> {
        let key = keys::encode_entity_key(tenant_id, entity_id);

        match self.storage.get(CF_ENTITIES, &key)? {
            Some(value) => {
                let entity: Entity = serde_json::from_slice(&value)?;
                Ok(Some(entity))
            }
            None => Ok(None),
        }
    }

    /// Update entity.
    pub fn update(&self, tenant_id: &str, entity: &Entity) -> Result<()> {
        // Same as insert (upsert semantics)
        self.insert(tenant_id, entity)
    }

    /// Delete entity (soft delete).
    pub fn delete(&self, tenant_id: &str, entity_id: Uuid) -> Result<()> {
        let mut entity = self
            .get(tenant_id, entity_id)?
            .ok_or(DatabaseError::EntityNotFound(entity_id))?;

        entity.deleted_at = Some(chrono::Utc::now());
        self.update(tenant_id, &entity)?;

        Ok(())
    }

    /// Scan all entities for tenant.
    pub fn scan(&self, tenant_id: &str) -> Result<Vec<Entity>> {
        let prefix = keys::encode_entity_prefix(tenant_id);
        let iter = self.storage.iter_prefix(CF_ENTITIES, &prefix)?;

        let mut entities = Vec::new();

        for (_key, value) in iter {
            let entity: Entity = serde_json::from_slice(&value)?;
            if !entity.is_deleted() {
                entities.push(entity);
            }
        }

        Ok(entities)
    }

    /// Scan entities by type.
    pub fn scan_by_type(&self, tenant_id: &str, entity_type: &str) -> Result<Vec<Entity>> {
        let all = self.scan(tenant_id)?;
        Ok(all
            .into_iter()
            .filter(|e| e.entity_type == entity_type)
            .collect())
    }
}
