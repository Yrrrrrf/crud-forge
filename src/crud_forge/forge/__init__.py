from typing import List, Type, Optional
from crud_forge.sql_types import get_eq_type
from sqlalchemy import Table, Enum as SQLAlchemyEnum
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel, Field, create_model, ConfigDict
from fastapi import APIRouter
from crud_forge.db import DatabaseManager
from crud_forge.forge.crud import *


Base = declarative_base()


# * API related Forge
class APIForge(BaseModel):
    db_manager: DatabaseManager = Field(...)  # Required field
    router: APIRouter = Field(default_factory=APIRouter)
    include_schemas: List[str] = Field(default_factory=list)
    exclude_tables: List[str] = Field(default_factory=list)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,  # any type is allowed ()
        extra='allow'  # allow extra fields (not defined in the model)
    )

    #  * private methods

    def _should_generate_routes(self, table: Table) -> bool:
        """
        Determine if routes should be generated for the given table based on
        include_schemas and exclude_tables configurations.
        """
        schema = table.schema or 'public'  # Default to 'public' if no schema is specified

        # Check if the table's schema is included (or if no schemas are specified)
        schema_included = not self.include_schemas or schema in self.include_schemas
        
        # Check if the table is not in the excluded list
        table_not_excluded = table.name not in self.exclude_tables

        return schema_included and table_not_excluded

    def _gen_table_routes(self, table: Table, db_dependency: Callable) -> None:
        """Generate CRUD routes for a single table."""
        def _get_pydantic_model(table: Table) -> Type[BaseModel]:
            """Generate or retrieve a Pydantic model for a given table."""
            fields = {
                column.name: (Optional[get_eq_type(str(column.type))], Field(default=None))
                for column in table.columns
            }
            return create_model(f"{table.name.upper()}_Pydantic", **fields)

        for route_generator in [create_route, get_route, update_route, delete_route]:
            route_generator(
                table=table,
                pydantic_model=_get_pydantic_model(table),
                router=self.router,
                db_dependency=db_dependency,
            )

    # * public methods

    def gen_routes(self) -> APIRouter:
        """Generate CRUD routes for all tables based on the configuration."""
        for _, table in self.db_manager.metadata.tables.items():
            if self._should_generate_routes(table):
                self._gen_table_routes(table, self.db_manager.get_db)
        return self.router

    # * logging methods

    def print_table(self, table: Table) -> None:
        """Print the structure of a single table in a compact, table-like format."""
        print(f"\t\033[0;96m {'public' if table.schema is None else table.schema}\033[0m.\033[1;96m{table.name}\033[0m")
        for column in table.columns:
            flags = []
            if column.primary_key:
                flags.append('\033[1;92mPK\033[0m')
            if column.foreign_keys:
                fk = next(iter(column.foreign_keys))
                flags.append(f'\033[1;94mFK -> {fk.column.table}\033[0m')
            if isinstance(column.type, SQLAlchemyEnum):
                flags.append(f'\033[93mEnum\033[1;93m({column.type.name})\033[0m')
                # ^ column.type.enums  *
                # ^ GET ALL ENUMS FROM THE ENUM TYPE IN THE COLUMN

            flags_str = ' '.join(flags)
            py_type = get_eq_type(str(column.type))
            nullable = "" if column.nullable else "*"
            
            print(f"\t\t{column.name:<20} {nullable:<2}\033[3;90m{str(column.type):<15}\033[0m \033[95m{py_type.__name__:<10}\033[0m {flags_str}")
            # SAME BUT ADD ITALICS TO THE TYPE NAME
            # print(f"\t\t{column.name:<20} {nullable:<2}\033[90m{str(column.type):<15}\033[0m \033[3;95m{py_type.__name__:<10}\033[0m {flags_str}")

        print()  # Add a blank line after each table

    def print_schema(self, schema: str) -> None:
        """Print the structure of all tables in a schema."""
        print(f"\033[1;97m[Schema] {schema}\033[0m")
        
        for table in self.db_manager.metadata.tables.values():
            if table.schema == schema:
                self.print_table(table)

    def print_db(self) -> None:
        """Print the structure of all tables in the database with schema grouping."""
        for schema in set(table.schema or 'public' for table in self.db_manager.metadata.tables.values()):
            print(f"\033[1;96m{schema}\033[0m")
            self.print_schema(schema)
