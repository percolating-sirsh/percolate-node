//! Schema validation and registry.
//!
//! Validates entities against Pydantic JSON schemas.

pub mod registry;
pub mod validator;
pub mod pydantic;
pub mod category;
pub mod builtin;

pub use registry::{SchemaRegistry, SchemaMetadata};
pub use validator::SchemaValidator;
pub use pydantic::{PydanticSchemaParser, ToolConfig, ResourceConfig};
pub use category::SchemaCategory;
pub use builtin::{
    register_builtin_schemas,
    schemas_table_schema,
    documents_table_schema,
    resources_table_schema,
    sessions_table_schema,
    messages_table_schema,
    feedback_table_schema,
};
