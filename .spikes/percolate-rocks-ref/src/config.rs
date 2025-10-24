//! Database configuration and location management.

use crate::types::error::{DatabaseError, Result};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

/// Database configuration entry.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DatabaseConfig {
    /// Database name.
    pub name: String,
    /// Path to database directory.
    pub path: PathBuf,
    /// Tenant ID (optional, defaults to database name).
    pub tenant: String,
}

/// Configuration manager for databases.
#[derive(Debug, Default, Serialize, Deserialize)]
pub struct Config {
    /// Map of database name to config.
    pub databases: HashMap<String, DatabaseConfig>,
}

impl Config {
    /// Get default config directory (~/.p8/).
    pub fn config_dir() -> Result<PathBuf> {
        let home = std::env::var("HOME")
            .map_err(|_| DatabaseError::ConfigError("HOME not set".to_string()))?;
        let dir = PathBuf::from(home).join(".p8");
        fs::create_dir_all(&dir)?;
        Ok(dir)
    }

    /// Get default database directory (~/.p8/db/).
    pub fn default_db_dir() -> Result<PathBuf> {
        let dir = Self::config_dir()?.join("db");
        fs::create_dir_all(&dir)?;
        Ok(dir)
    }

    /// Get config file path (~/.p8/config.json).
    pub fn config_file() -> Result<PathBuf> {
        Ok(Self::config_dir()?.join("config.json"))
    }

    /// Load configuration from file.
    pub fn load() -> Result<Self> {
        let config_file = Self::config_file()?;

        if config_file.exists() {
            let content = fs::read_to_string(&config_file)?;
            let config: Config = serde_json::from_str(&content)
                .map_err(|e| DatabaseError::ConfigError(format!("Invalid config: {}", e)))?;
            Ok(config)
        } else {
            Ok(Self::default())
        }
    }

    /// Save configuration to file.
    pub fn save(&self) -> Result<()> {
        let config_file = Self::config_file()?;
        let content = serde_json::to_string_pretty(self)
            .map_err(|e| DatabaseError::ConfigError(format!("Serialize error: {}", e)))?;
        fs::write(&config_file, content)?;
        Ok(())
    }

    /// Register a database with a name and path.
    pub fn register(&mut self, name: String, path: PathBuf, tenant: Option<String>) -> Result<()> {
        let tenant = tenant.unwrap_or_else(|| name.clone());
        let config = DatabaseConfig {
            name: name.clone(),
            path,
            tenant,
        };
        self.databases.insert(name, config);
        self.save()?;
        Ok(())
    }

    /// Get database config by name.
    pub fn get(&self, name: &str) -> Result<&DatabaseConfig> {
        self.databases.get(name).ok_or_else(|| {
            DatabaseError::ConfigError(format!(
                "Database '{}' not found. Run: rem-db init {}",
                name, name
            ))
        })
    }

    /// List all registered databases.
    pub fn list(&self) -> Vec<&DatabaseConfig> {
        self.databases.values().collect()
    }

    /// Resolve database path from name.
    /// If name is registered, use config path.
    /// Otherwise, check if it's a direct path.
    pub fn resolve_path(&self, name_or_path: &str) -> Result<(PathBuf, String)> {
        // First, try as database name
        if let Ok(config) = self.get(name_or_path) {
            return Ok((config.path.clone(), config.tenant.clone()));
        }

        // If it's a path, use it directly
        let path = PathBuf::from(name_or_path);
        if path.exists() {
            let tenant = path
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("default")
                .to_string();
            return Ok((path, tenant));
        }

        Err(DatabaseError::ConfigError(format!(
            "Database '{}' not found and path does not exist",
            name_or_path
        )))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn test_config_register_and_get() {
        let mut config = Config::default();
        let path = PathBuf::from("/tmp/test-db");

        config.register("test".to_string(), path.clone(), None).ok();

        let db_config = config.get("test").unwrap();
        assert_eq!(db_config.name, "test");
        assert_eq!(db_config.path, path);
        assert_eq!(db_config.tenant, "test"); // Default tenant = name
    }

    #[test]
    fn test_config_resolve_path() {
        let mut config = Config::default();
        let path = PathBuf::from("/tmp/my-db");

        config.register("mydb".to_string(), path.clone(), Some("tenant1".to_string())).ok();

        let (resolved_path, tenant) = config.resolve_path("mydb").unwrap();
        assert_eq!(resolved_path, path);
        assert_eq!(tenant, "tenant1");
    }
}
