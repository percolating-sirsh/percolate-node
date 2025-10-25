//! Schema category types for organization and permissions.

use serde::{Deserialize, Serialize};

/// Schema category for organization and access control.
///
/// Categories organize schemas by purpose and visibility:
/// - **System**: Built-in schemas (resources, documents, schemas)
/// - **Agents**: Agent-let schemas (carrier.agents.cda_mapper)
/// - **Public**: Shared user schemas (visible across tenants)
/// - **User**: Private user schemas (tenant-scoped)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SchemaCategory {
    /// Built-in system schemas (resources, documents, schemas table)
    System,

    /// Agent-let schemas with MCP tools and resources
    Agents,

    /// Shared user schemas (visible across tenants)
    Public,

    /// Private user schemas (tenant-scoped)
    User,
}

impl SchemaCategory {
    /// Parse category from string.
    ///
    /// # Arguments
    ///
    /// * `s` - Category string ("system", "agents", "public", "user")
    ///
    /// # Returns
    ///
    /// Parsed category or None if invalid
    ///
    /// # Example
    ///
    /// ```
    /// let cat = SchemaCategory::from_str("agents");
    /// assert_eq!(cat, Some(SchemaCategory::Agents));
    /// ```
    pub fn from_str(s: &str) -> Option<Self> {
        match s.to_lowercase().as_str() {
            "system" => Some(Self::System),
            "agents" => Some(Self::Agents),
            "public" => Some(Self::Public),
            "user" => Some(Self::User),
            _ => None,
        }
    }

    /// Convert category to string.
    ///
    /// # Returns
    ///
    /// Category as lowercase string
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::System => "system",
            Self::Agents => "agents",
            Self::Public => "public",
            Self::User => "user",
        }
    }
}

impl Default for SchemaCategory {
    /// Default category is User.
    fn default() -> Self {
        Self::User
    }
}

impl std::fmt::Display for SchemaCategory {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_category_from_str() {
        assert_eq!(SchemaCategory::from_str("system"), Some(SchemaCategory::System));
        assert_eq!(SchemaCategory::from_str("agents"), Some(SchemaCategory::Agents));
        assert_eq!(SchemaCategory::from_str("public"), Some(SchemaCategory::Public));
        assert_eq!(SchemaCategory::from_str("user"), Some(SchemaCategory::User));
        assert_eq!(SchemaCategory::from_str("invalid"), None);
    }

    #[test]
    fn test_category_as_str() {
        assert_eq!(SchemaCategory::System.as_str(), "system");
        assert_eq!(SchemaCategory::Agents.as_str(), "agents");
    }

    #[test]
    fn test_default_category() {
        assert_eq!(SchemaCategory::default(), SchemaCategory::User);
    }
}
