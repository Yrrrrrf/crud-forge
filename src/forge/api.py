"""
APIForge: Enhanced API route generation with proper model handling.
Integrates with ModelForge for model management and route generation.
"""
from typing import Dict, List, Optional, Type, Union, Set
from fastapi import APIRouter
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import Table, inspect
from .model import ModelForge
from .gen.crud import gen_crud, get_route
import logging
from forge.utils import *

logger = logging.getLogger(__name__)

class RouteType(str, Enum):
    """Available route types."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"

class APIConfig(BaseModel):
    """Configuration for API route generation."""
    include_schemas: List[str] = Field(default_factory=list)
    exclude_tables: List[str] = Field(default_factory=list)
    route_prefix: str = Field(default="")
    enable_tags: bool = Field(default=True)
    view_operations: List[RouteType] = Field(default_factory=lambda: [RouteType.READ])
    
    model_config = ConfigDict(
        json_schema_extra = {
            "example": {
                "include_schemas": ["public", "pharma"],
                "exclude_tables": ["alembic_version"],
                "route_prefix": "/api/v1",
                "enable_tags": True,
                "view_operations": ["read"]
            }
        }
    )

class TableInfo(BaseModel):
    """Stores information about database tables and views."""
    name: str
    schema: str
    is_view: bool
    column_names: List[str]
    primary_keys: Set[str]
    foreign_keys: Dict[str, str]  # column_name -> referenced_table

    model_config = ConfigDict(arbitrary_types_allowed=True)

class APIForge(BaseModel):
    """
    Manages API route generation and CRUD operations.
    Works in conjunction with ModelForge for model handling.
    """
    model_forge: ModelForge
    config: APIConfig = Field(default_factory=APIConfig)
    routers: Dict[str, APIRouter] = Field(default_factory=dict)
    table_info: Dict[str, TableInfo] = Field(default_factory=dict)
    processed_tables: Set[str] = Field(default_factory=set)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        self._initialize_routers()
        self._analyze_tables()

    def _initialize_routers(self) -> None:
        """Initialize routers for each schema."""
        schemas = self._get_schemas()
        
        for schema in schemas:
            # Create schema router
            prefix = f"{self.config.route_prefix}/{schema}" if schema != "public" else self.config.route_prefix
            
            # Main schema router
            self.routers[schema] = APIRouter(
                prefix=prefix,
                tags=[schema.upper()]
            )
            
            # Views router
            self.routers[f"{schema}_views"] = APIRouter(
                prefix=f"{prefix}/views",
                tags=[f"{schema.upper()}_VIEWS"]
            )

    def _get_schemas(self) -> List[str]:
        """Get relevant schemas based on configuration."""
        db_schemas = {
            table.schema or 'public' 
            for table in self.model_forge.db_manager.metadata.tables.values()
        }
        
        if self.config.include_schemas:
            return sorted(set(self.config.include_schemas) & db_schemas)
        return sorted(db_schemas)

    def _analyze_tables(self) -> None:
        """Analyze database tables and views."""
        inspector = inspect(self.model_forge.db_manager.engine)
        
        for table in self.model_forge.db_manager.metadata.tables.values():
            schema = table.schema or 'public'
            is_view = table.name in self.model_forge.db_manager.view_names
            
            # Get column information
            columns = table.columns
            pk_cols = {col.name for col in table.primary_key}
            fk_dict = {
                fk.parent.name: f"{fk.column.table.name}.{fk.column.name}"
                for col in columns
                for fk in col.foreign_keys
            }
            
            # Store table information
            self.table_info[f"{schema}.{table.name}"] = TableInfo(
                name=table.name,
                schema=schema,
                is_view=is_view,
                column_names=[col.name for col in columns],
                primary_keys=pk_cols,
                foreign_keys=fk_dict
            )

    def generate_routes(self) -> None:
        """Generate routes for all tables and views in the database.
        Tables get full CRUD operations while views typically get read-only routes."""
        for full_name, info in self.table_info.items():
            # Skip excluded tables
            if info.name in self.config.exclude_tables:
                logger.info(f"Skipping excluded table/view: {full_name}")
                continue

            try:
                logger.info(f"Processing {full_name} ({'view' if info.is_view else 'table'})")
                
                # Check if this is a view by looking for the 'v_' prefix
                # This ensures consistent view detection
                if info.is_view or info.name.startswith('v_'):
                    # self._generate_view_routes(info)
                    pass
                else: self._generate_table_routes(info)

                self.processed_tables.add(info.name)
                logger.info(f"Successfully generated routes for {full_name}")
                
            except Exception as e:
                logger.error(f"Failed to generate routes for {full_name}: {str(e)}")

    def _generate_table_routes(self, info: TableInfo) -> None:
        """Generate CRUD routes for regular database tables.
        
        Args:
            info (TableInfo): Table information including schema and name
            
        Note:
            - Uses ModelForge to get Pydantic and SQLAlchemy models
            - Generates all CRUD operations (Create, Read, Update, Delete)
            - Routes are added to the schema's main router
        """
        # Construct the full table name with schema
        full_table_name = f"{info.schema}.{info.name}"
        
        try:
            # Get the SQLAlchemy Table object
            table = self.model_forge.db_manager.metadata.tables[full_table_name]
            # Get both Pydantic and SQLAlchemy models from ModelForge
            # The models are stored as a tuple (pydantic_model, sqlalchemy_model)
            if full_table_name not in self.model_forge.models:
                raise KeyError(f"No models found for {full_table_name}")
                
            pydantic_model, sqlalchemy_model = self.model_forge.models[full_table_name]
            print(f"{table}\n\t{pydantic_model.__name__}\n\t{sqlalchemy_model.__name__}")

            # Generate all CRUD routes using the gen_crud utility
            gen_crud(
                table=table,
                pydantic_model=pydantic_model,
                sqlalchemy_model=sqlalchemy_model,
                router=self.routers[info.schema],  # Use the schema's main router
                db_dependency=self.model_forge.db_manager.get_db,
                tags=[info.schema.upper()] if self.config.enable_tags else None
            )
            
        except Exception as e:
            logger.error(f"Error generating routes for table {full_table_name}: {str(e)}")
            raise

    # def _generate_view_routes(self, info: TableInfo) -> None:
    #     """Generate routes for database views (typically read-only).
        
    #     Args:
    #         info (TableInfo): View information including schema and name
            
    #     Note:
    #         - Only generates routes for operations allowed in view_operations
    #         - By default, only READ operations are allowed on views
    #         - Routes are added to the schema's views router
    #     """
    #     # Check if read operations are allowed for views
    #     if RouteType.READ not in self.config.view_operations:
    #         logger.info(f"Skipping view {info.name} - READ operation not enabled")
    #         return

    #     # Construct the full view name with schema
    #     full_view_name = f"{info.schema}.{info.name}"
        
    #     try:
    #         # Get the SQLAlchemy Table object representing the view
    #         table = self.model_forge.db_manager.metadata.tables[full_view_name]
    #         logger.debug(f"Retrieved view object for {full_view_name}")
            
    #         # Get both Pydantic and SQLAlchemy models from ModelForge
    #         if full_view_name not in self.model_forge.models:
    #             raise KeyError(f"No models found for view {full_view_name}")
                
    #         pydantic_model, sqlalchemy_model = self.model_forge.models[full_view_name]
    #         logger.debug(f"Retrieved models for view {full_view_name}")

    #         # Generate only the READ route for the view
    #         get_route(
    #             table=table,
    #             pydantic_model=pydantic_model,
    #             sqlalchemy_model=sqlalchemy_model,
    #             router=self.routers[f"{info.schema}_views"],  # Use the schema's views router
    #             db_dependency=self.model_forge.db_manager.get_db,
    #             tags=[f"{info.schema.upper()}_VIEWS"] if self.config.enable_tags else None
    #         )
            
    #     except Exception as e:
    #         logger.error(f"Error generating routes for view {full_view_name}: {str(e)}")
    #         raise

    # def get_router(self, schema: str) -> APIRouter:
    #     """Get router for a specific schema."""
    #     if schema not in self.routers: raise ValueError(f"Schema '{schema}' not found")
    #     return self.routers[schema]

    # def get_routes_summary(self) -> Dict[str, List[str]]:
    #     """Get summary of generated routes."""
    #     summary = {}
    #     for schema, router in self.routers.items():
    #         routes = []
    #         for route in router.routes: routes.append(f"{route.methods} {route.path}")
    #         summary[schema] = routes
    #     return summary

    # def print_routes(self) -> None:
    #     """Print all generated routes in a structured format."""
    #     print("\nGenerated Routes:")
    #     for schema, router in self.routers.items():
    #         print(f"\n{yellow(f'[Schema] {schema}')}")
    #         for route in router.routes:
    #             methods = ", ".join(route.methods)
    #             print(f"  {cyan(f'{methods:<10}')} {route.path}")
