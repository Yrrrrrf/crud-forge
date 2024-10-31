"""
ModelForge: Enhanced model management for database entities.
Handles Pydantic and SQLAlchemy model generation, caching, and type mapping.
"""
from typing import Dict, List, Optional, Set, Type, Any
from dataclasses import dataclass
from pydantic import BaseModel, Field, ConfigDict, create_model
from sqlalchemy import Column, Table, Enum as SQLAlchemyEnum
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.declarative import declared_attr
from enum import Enum as PyEnum
import logging
from .db import DBForge
from .utils import *

logger = logging.getLogger(__name__)

@dataclass
class EnumInfo:
    """Store information about database enums."""
    name: str
    values: List[str]
    python_enum: Optional[Type[PyEnum]] = None
    schema: Optional[str] = None

    def create_enum(self) -> Type[PyEnum]:
        """Create a Python Enum from the enum information."""
        if not self.python_enum:
            self.python_enum = PyEnum(self.name, {v: v for v in self.values})
        return self.python_enum

class BaseSQLModel(DeclarativeBase):
    """Base class for all generated SQLAlchemy models."""
    
    @declared_attr
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        return cls.__name__.lower()

    @classmethod
    def get_fields(cls) -> Dict[str, Any]:
        """Get all model fields."""
        return {
            column.name: column for column in cls.__table__.columns
        }

class ModelForge(BaseModel):
    """
    Manages model generation and caching for database entities.
    Handles both Pydantic and SQLAlchemy models with support for enums.
    """
    db_manager: DBForge = Field(..., description="Database manager instance")
    include_schemas: List[str] = Field(default_factory=list)
    exclude_tables: List[str] = Field(default_factory=list)

    # Caches
    models: Dict[str, tuple[Type[BaseModel], Type[BaseSQLModel]]] = Field(default_factory=dict)
    enum_cache: Dict[str, EnumInfo] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')

    def __init__(self, **data):
        super().__init__(**data)
        self._load_enums()
        # * register models
        for table in self.db_manager.metadata.tables.values():
            match table.name.startswith('v_') or table.name in self.db_manager.view_names:
                case True: continue # * do not register views
                case False: self.register_models(table)

    def _load_enums(self) -> None:
        """Load and cache enum types from database, properly handling views."""
        # First pass: collect all unique enum value sets from base tables
        for table in self.db_manager.metadata.tables.values():
            # Skip views in the first pass
            if table.name.startswith('v_') or table.name in (self.db_manager.view_names or set()):
                continue

            for column in table.columns:
                if isinstance(column.type, SQLAlchemyEnum):
                    # enum_values = tuple(sorted(column.type.enums))  # Make hashable
                    enum_name = f"{column.name}_enum"  # Simplified naming
                    
                    # Create the enum only for base tables
                    if enum_name not in self.enum_cache:
                        try:
                            python_enum = PyEnum(enum_name, {v: v for v in column.type.enums})
                            self.enum_cache[enum_name] = EnumInfo(
                                name=enum_name,
                                values=list(column.type.enums),
                                python_enum=python_enum
                            )
                            logger.info(f"Created enum: {enum_name} with values {column.type.enums}")
                        except Exception as e:
                            logger.warning(f"Failed to create enum {enum_name}: {str(e)}")

    def _get_enum_for_column(self, table: Table, column_name: str) -> Optional[Type[PyEnum]]:
        """Get enum type for a column, reusing base table enums for views."""
        column = table.columns[column_name]
        if not isinstance(column.type, SQLAlchemyEnum):
            return None
                
        # For base tables, use direct lookup
        enum_name = f"{column_name}_enum"
        return self.enum_cache.get(enum_name, None).python_enum if enum_name in self.enum_cache else None

    def register_models(self, table: Table) -> tuple[Type[BaseModel], Type[BaseSQLModel]]:
        """Generate and register both Pydantic and SQLAlchemy models for a table."""
        table_name = f"{table.schema}.{table.name}"
        if table_name in self.models: return self.models[table_name]

        fields = {}
        for column in table.columns:
            enum_type = self._get_enum_for_column(table, column.name)
            if enum_type:
                field_type = enum_type
            else:
                field_type = get_eq_type(str(column.type))
            
            fields[column.name] = (
                Optional[field_type] if column.nullable else field_type,
                Field(default=None if column.nullable else ...)
            )

        pydantic_model = create_model(
            f"Pydantic_{table.name}",
            __config__=ConfigDict(from_attributes=True),
            **fields
        )

        sqlalchemy_model = self._get_sqlalchemy_model(table)
        self.models[table_name] = pydantic_model, sqlalchemy_model
        return pydantic_model, sqlalchemy_model

    def get_enum_for_column(self, table_name: str, column_name: str) -> Optional[Type[PyEnum]]:
        """Get the appropriate enum type for a column, handling both tables and views."""
        enum_name = f"{table_name}_{column_name}_enum"
            
        # Check direct enum cache
        if enum_name in self.enum_cache:
            return self.enum_cache[enum_name].python_enum
            
        return None

    def _create_pydantic_model(self, table: Table) -> Type[BaseModel]:
        """Create a Pydantic model with proper enum handling for views."""
        model_name = f"Pydantic_{table.name}"
        fields = {}
        
        for column in table.columns:
            field_type: Type
            
            if isinstance(column.type, SQLAlchemyEnum):
                enum_type = self.get_enum_for_column(table.name, column.name)
                field_type = enum_type if enum_type else str
            else: field_type = get_eq_type(str(column.type))

            fields[column.name] = (
                Optional[field_type] if column.nullable else field_type,
                Field(description=getattr(column, 'comment', None))
            )

        return create_model(
            model_name,
            __config__=ConfigDict(from_attributes=True),
            **fields
        )

    def _get_sqlalchemy_model(
        self,
        table: Table,
        include_columns: Optional[List[str]] = None,
        exclude_columns: Optional[List[str]] = None,
        custom_columns: Optional[Dict[str, Column]] = None
    ) -> Type[BaseSQLModel]:
        """
        Generate or retrieve a cached SQLAlchemy model for a given table.
        """
        if table.name in self.models: return self.models[table.name][1]

        class_attrs: Dict[str, Any] = {
            '__table__': table,
            '__tablename__': table.name,
        }

        # Process columns based on include and exclude lists
        for column in table.columns:
            if (include_columns is None or column.name in include_columns) and \
               (exclude_columns is None or column.name not in exclude_columns):
                class_attrs[column.name] = column

        # Add or override with custom columns
        if custom_columns: class_attrs.update(custom_columns)
        return type( f"SQLAlchemy_{table.name.lower()}", (BaseSQLModel,), class_attrs )

    def log_schema_structure(self) -> None:
        print(f"\n{bold('Schema Structure:')}")
        schemas = set(table.schema for table in self.db_manager.metadata.tables.values())
        
        for schema in sorted(schemas):
            print(f"\n{yellow(f'[Schema]{schema or 'public'}')}")            
            schema_tables = [table for table in self.db_manager.metadata.tables.values() if table.schema == schema]
            
            regular_tables = [t for t in schema_tables if t.name not in self.db_manager.view_names]
            views = [t for t in schema_tables if t.name in self.db_manager.view_names]
           
            [print_table_structure(t) for t in (regular_tables + views)]


def get_column_flags(column: Column) -> List[str]:
    """Get formatted flags for a column."""
    flags = []
    if column.primary_key: flags.append(f'{green("PK")}')
    if column.foreign_keys: flags.append(f'{blue(f"FK → {next(iter(column.foreign_keys)).column.table}")}')
    if isinstance(column.type, SQLAlchemyEnum): flags.append(f'{yellow(f"Enum({column.type.name})")}')
    return flags


def print_table_structure(table: Table) -> None:
    """Print detailed table structure with columns and enums."""
    schema_name = table.schema or 'public'
    # todo: PAY ATTENTION TO THIS...
    # todo: TO HANDLE THEM AS VIEWS THEY MUST START WITH 'v_'
    # todo: RegEx: ^v_.*$
    is_view = table.name.startswith('v_')  # Check if it's a view
    table_type = "VIEW" if is_view else "TABLE"
    print(f"\t{cyan(schema_name)}.{bold(cyan(table.name))} ({yellow(table_type)})")
    
    # Print columns
    for column in table.columns:
        flags = get_column_flags(column)
        flags_str = ' '.join(flags)
        py_type = get_eq_type(str(column.type))
        nullable = "" if column.nullable else "*"
        
        # Check for enum type
        if isinstance(column.type, SQLAlchemyEnum):
            type_str = f"{yellow(column.type.name)}"
            values = f"{gray(str(column.type.enums))}"
        else: type_str = magenta(py_type.__name__)

        print(f"\t\t{column.name:<24} {red(f'{nullable:<2}')}{gray(str(column.type)[:20]):<32} "
              f"{type_str:<8} {flags_str} {values if 'values' in locals() else ''}")

    print()
