"""Schema registry for REM database - agent-let aware schemas."""

from typing import Any, Optional, Type

from pydantic import BaseModel, ConfigDict, Field


class MCPTool(BaseModel):
    """MCP tool reference for schema operations."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    server: Optional[str] = Field(None, description="MCP server name")
    usage: Optional[str] = Field(None, description="Usage instructions")


class Schema(BaseModel):
    """Schema definition for a REM entity type (agent-let aware).

    This stores the full Pydantic JSON schema export, following the carrier
    agent-let pattern. The JSON schema includes:
    - System prompt (from model docstring) in 'description'
    - Field definitions with types, descriptions, constraints in 'properties'
    - Nested models in '$defs'
    - Agent-let metadata in top-level fields (from model_config.json_schema_extra)
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",  # Allow extra fields from JSON schema
        populate_by_name=True,  # Allow both field name and alias
    )

    # Core identification (from model_config.json_schema_extra)
    name: str = Field(description="Schema name (table name)")
    fully_qualified_name: Optional[str] = Field(
        None, description="Fully qualified name (e.g., 'carrier.agents.module.Class')"
    )
    short_name: Optional[str] = Field(None, description="Short name for URI")
    version: Optional[str] = Field(None, description="Semantic version (e.g., '1.0.0')")
    category: str = Field(
        default="user",
        description="Schema category (system, agents, public, user)"
    )

    # JSON Schema standard fields
    title: Optional[str] = Field(None, description="Schema title (class name)")
    description: Optional[str] = Field(
        None, description="System prompt from model docstring"
    )
    type: str = Field(default="object", description="JSON schema type")
    properties: dict[str, Any] = Field(
        default_factory=dict, description="Field definitions (JSON schema)"
    )
    required: list[str] = Field(default_factory=list, description="Required field names")
    defs: Optional[dict[str, Any]] = Field(
        None, alias="$defs", description="Nested model definitions"
    )

    # Agent-let metadata (from model_config.json_schema_extra)
    indexed_fields: list[str] = Field(
        default_factory=list, description="Fields to create indexes on"
    )
    tools: list[MCPTool] = Field(
        default_factory=list, description="MCP tools available for this entity type"
    )

    # Runtime-only (not serialized)
    pydantic_model: Optional[Type[BaseModel]] = Field(
        None, exclude=True, description="Associated Pydantic model"
    )

    @classmethod
    def from_pydantic(
        cls,
        name: str,
        model: Type[BaseModel],
        description: Optional[str] = None,
        system_prompt: Optional[str] = None,
        indexed_fields: Optional[list[str]] = None,
        mcp_tools: Optional[list[MCPTool]] = None,
    ) -> "Schema":
        """Create schema from Pydantic model using full JSON schema export.

        This follows the carrier agent-let pattern:
        1. Export full JSON schema with model.model_json_schema()
        2. Extract metadata from model_config.json_schema_extra
        3. System prompt from model docstring (in 'description' field)
        4. All field metadata from Pydantic Field() definitions

        Args:
            name: Schema name (table name)
            model: Pydantic model class
            description: Override description (default: use docstring)
            system_prompt: Legacy parameter (use model docstring instead)
            indexed_fields: Fields to index (appended to model_config values)
            mcp_tools: MCP tools (appended to model_config values)

        Returns:
            Schema instance with full JSON schema
        """
        # Export full JSON schema
        json_schema = model.model_json_schema()

        # Extract metadata from model_config.json_schema_extra
        extra = {}
        if hasattr(model, "model_config"):
            config_dict = model.model_config
            if isinstance(config_dict, dict) and "json_schema_extra" in config_dict:
                extra = config_dict["json_schema_extra"]
            elif hasattr(config_dict, "get"):
                extra = config_dict.get("json_schema_extra", {})

        # Build Schema from JSON schema + extra metadata
        fully_qualified_name = extra.get("fully_qualified_name")
        short_name = extra.get("short_name", name)
        version = extra.get("version", "1.0.0")
        category = extra.get("category", "user")

        # MCP tools from extra + parameter
        tools_extra = extra.get("tools", [])
        tools_combined = [MCPTool(**t) if isinstance(t, dict) else t for t in tools_extra]
        if mcp_tools:
            tools_combined.extend(mcp_tools)

        # Indexed fields from extra + parameter
        indexed_extra = extra.get("indexed_fields", [])
        indexed_combined = list(set(indexed_extra + (indexed_fields or [])))

        # System prompt: priority is description param, then system_prompt param, then docstring
        final_description = (
            description
            or system_prompt
            or json_schema.get("description")
            or model.__doc__
            or f"{name} entity"
        )

        # Extract $defs separately (handle both dict key and field name)
        defs_data = json_schema.get("$defs")

        return cls(
            name=name,
            fully_qualified_name=fully_qualified_name,
            short_name=short_name,
            version=version,
            category=category,
            title=json_schema.get("title"),
            description=final_description,
            type=json_schema.get("type", "object"),
            properties=json_schema.get("properties", {}),
            required=json_schema.get("required", []),
            defs=defs_data,  # Use explicit variable
            indexed_fields=indexed_combined,
            tools=tools_combined,
            pydantic_model=model,
        )

    def validate_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Validate data against schema.

        Args:
            data: Entity data

        Returns:
            Validated data

        Raises:
            ValidationError: If data doesn't match schema
        """
        if self.pydantic_model:
            # Use Pydantic validation
            validated = self.pydantic_model(**data)
            return validated.model_dump()
        else:
            # Manual validation using JSON schema (simplified)
            validated = {}
            for field_name, field_schema in self.properties.items():
                if field_name in data:
                    validated[field_name] = data[field_name]
                elif field_name in self.required:
                    default = field_schema.get("default")
                    if default is None:
                        raise ValueError(f"Missing required field: {field_name}")
                    validated[field_name] = default

            return validated

    def get_indexed_fields(self) -> list[str]:
        """Get list of indexed field names."""
        return self.indexed_fields

    def to_json_schema(self) -> dict[str, Any]:
        """Export as standard JSON schema.

        Returns:
            JSON schema dict
        """
        schema = {
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "properties": self.properties,
            "required": self.required,
        }

        if self.defs:
            schema["$defs"] = self.defs

        # Add agent-let metadata
        if self.fully_qualified_name:
            schema["fully_qualified_name"] = self.fully_qualified_name
        if self.short_name:
            schema["short_name"] = self.short_name
        if self.version:
            schema["version"] = self.version
        if self.category:
            schema["category"] = self.category
        if self.tools:
            schema["tools"] = [t.model_dump() for t in self.tools]
        if self.indexed_fields:
            schema["indexed_fields"] = self.indexed_fields

        return schema
