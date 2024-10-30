from typing import List, Dict, Type, Optional, Callable, Any, Tuple

# * module main components
# * here modifications can be made to the main components of the module...
# * so that the module can be used as a package


from forge.db import DBForge, DBConfig

from forge.gen.crud import create_route, get_route, update_route, delete_route, gen_crud

from sqlalchemy import Column, Table, Enum as SQLAlchemyEnum
from enum import Enum as PyEnum
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel, Field, create_model, ConfigDict
from fastapi import APIRouter, HTTPException
from forge.utils.sql_types import get_eq_type

Base = declarative_base()


class EnumInfo:
    def __init__(self, name: str, values: List[str], python_enum: Type[PyEnum]):
        self.name = name
        self.values = values
        self.python_enum = python_enum

class APIForge(BaseModel):
    db_manager: DBForge = Field(...)
    router: APIRouter = Field(default_factory=APIRouter)
    include_schemas: List[str] = Field(default_factory=list)
    exclude_tables: List[str] = Field(default_factory=list)
    pydantic_models: Dict[str, Type[BaseModel]] = Field(default_factory=dict)
    sqlalchemy_models: Dict[str, Type[Base]] = Field(default_factory=dict)
    enum_cache: Dict[str, EnumInfo] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True, extra='allow')

    def __init__(self, **data):
        super().__init__(**data)
        self._load_enums()

    def _load_enums(self):
        for table in self.db_manager.metadata.tables.values():
            for column in table.columns:
                if isinstance(column.type, SQLAlchemyEnum):
                    enum_name = f"{table.name}_{column.name}_enum"
                    if enum_name not in self.enum_cache:
                        values = column.type.enums
                        python_enum = PyEnum(enum_name, {v: v for v in values})
                        self.enum_cache[enum_name] = EnumInfo(enum_name, values, python_enum)

    def _get_enum_for_column(self, table: Table, column_name: str) -> Optional[Type[PyEnum]]:
        enum_info = self.enum_cache.get(f"{table.name}_{column_name}_enum")
        # if not, build the enum from the column metadata
        if not enum_info:  #if there is no enum info, build it
            column = table.columns[column_name]  # get the column object
            if isinstance(column.type, SQLAlchemyEnum):  # check if the column type is an enum
                enum_info = EnumInfo(f"{table.name}_{column_name}_enum", column.type.enums, None)  # build the enum info
                self.enum_cache[enum_info.name] = enum_info  # * update the enum cache
        return enum_info.python_enum if enum_info else None

    def _get_pydantic_model(self, table: Table) -> Type[BaseModel]:
        if table.name in self.pydantic_models:
            return self.pydantic_models[table.name]

        fields = {}
        for column in table.columns:
            enum_type = self._get_enum_for_column(table, column.name)
            if enum_type:  # Use the enum type if available
                fields[column.name] = (Optional[enum_type], Field(default=None))
            else:  # Otherwise, use the equivalent Python type
                python_type = get_eq_type(str(column.type))
                fields[column.name] = (Optional[python_type], Field(default=None))

        model = create_model(f"{table.name.upper()}_Pydantic", **fields)
        self.pydantic_models[table.name] = model
        return model

    def _get_sqlalchemy_model(
        self,
        table: Table, 
        include_columns: Optional[list[str]] = None,
        exclude_columns: Optional[list[str]] = None,
        custom_columns: Optional[Dict[str, Column]] = None
    ) -> Type[Base]:
        """
        Generate or retrieve a cached SQLAlchemy model for a given table.

        Args:
            table (Table): The SQLAlchemy Table object.
            include_columns (Optional[list[str]]): List of column names to include. If None, include all.
            exclude_columns (Optional[list[str]]): List of column names to exclude.
            custom_columns (Optional[Dict[str, Column]]): Custom column definitions to override or add.

        Returns:
            Type[Base]: The generated SQLAlchemy model class.
        """
        if table.name in self.sqlalchemy_models:
            return self.sqlalchemy_models[table.name]

        class_attrs: Dict[str, Any] = {
            '__tablename__': table.name,
            '__table__': table,
        }

        # Check if it's a view
        if self.db_manager.is_view(f"{table.schema}.{table.name}" if table.schema else table.name):
            # For views, we need to:
            # 1. Set abstract=True to prevent SQLAlchemy from validating the primary key
            class_attrs['__abstract__'] = True
            # 2. Mark it as a view
            class_attrs['__is_view__'] = True

        # Process columns based on include and exclude lists
        for column in table.columns:
            if (include_columns is None or column.name in include_columns) and \
            (exclude_columns is None or column.name not in exclude_columns):
                class_attrs[column.name] = column

        # Add or override with custom columns
        if custom_columns:
            class_attrs.update(custom_columns)

        # Create the model class
        ModelClass = type(f"{table.name.capitalize()}Model", (Base,), class_attrs)

        self.sqlalchemy_models[table.name] = ModelClass
        return ModelClass

    def _should_generate_routes(self, table: Table) -> bool:
        schema = table.schema or 'public'
        schema_included = not self.include_schemas or schema in self.include_schemas
        table_not_excluded = table.name not in self.exclude_tables
        return schema_included and table_not_excluded

    def _genr_table_crud(self, table: Table, db_dependency: Callable) -> None:
        pydantic_model = self._get_pydantic_model(table)
        sqlalchemy_model = self._get_sqlalchemy_model(table)

        for route_generator in [create_route, get_route, update_route, delete_route]:
            route_generator(
                table=table,
                pydantic_model=pydantic_model,
                sqlalchemy_model=sqlalchemy_model,
                router=self.router,
                db_dependency=db_dependency
            )

    def genr_crud(self) -> APIRouter:
        for _, table in self.db_manager.metadata.tables.items():
            if self._should_generate_routes(table):
                self._genr_table_crud(table, self.db_manager.get_db)
        return self.router

    def _print_table_with_enums(self, table: Table) -> None:
        """Print the structure of a single table with its enums."""
        print(f"\t\033[0;96m{table.schema or 'public'}\033[0m.\033[1;96m{table.name}\033[0m")
        
        # Print columns
        for column in table.columns:
            flags = self._get_column_flags(column)
            flags_str = ' '.join(flags)
            py_type = get_eq_type(str(column.type))
            nullable = "" if column.nullable else "*"
            print(f"\t\t{column.name:<20} {nullable:<2}\033[3;90m{str(column.type):<15}\033[0m \033[95m{py_type.__name__:<10}\033[0m {flags_str}")
        
        # Print enums
        enum_columns = [column for column in table.columns if isinstance(column.type, SQLAlchemyEnum)]
        if enum_columns:
            for column in enum_columns:
                enum_name = f"{table.name}_{column.name}_enum"
                enum_info = self.enum_cache.get(enum_name)
                if enum_info:
                    # print(f"\t\t\033[1;93m* {column.name}\033[0m: {', '.join(enum_info.values)}")
                    # same but now print the vales in light yellow
                    print(f"\t\t\033[1;93m* {column.name}\033[0m: \033[93m{', '.join(enum_info.values)}\033[0m")
        
        print()  # Add a blank line after each table

    def _get_column_flags(self, column: Column) -> List[str]:
        """Get the flags for a column."""
        flags = []
        if column.primary_key:
            flags.append('\033[1;92mPK\033[0m')
        if column.foreign_keys:
            fk = next(iter(column.foreign_keys))
            flags.append(f'\033[1;94mFK -> {fk.column.table}\033[0m')
        if isinstance(column.type, SQLAlchemyEnum):
            flags.append(f'\033[93mEnum({column.type.name})\033[0m')
        return flags

    def p_schemas(self, schemas: List[str]) -> None:
        """Print the structure of all tables and enums in a list of schemas."""
        for schema in schemas:
            print(f"\n\033[1;93m[Schema]{schema}\033[0m")
            tables = [table for table in self.db_manager.metadata.tables.values() if table.schema == schema]
            for table in tables:
                self._print_table_with_enums(table)
            print()  # Add a blank line after each schema


# * logging methods


def p_table(table: Table) -> None:
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

        flags_str = ' '.join(flags)
        py_type = get_eq_type(str(column.type))
        nullable = "" if column.nullable else "*"

        print(f"\t\t{column.name:<20} {nullable:<2}\033[3;90m{str(column.type):<15}\033[0m \033[95m{py_type.__name__:<10}\033[0m {flags_str}")

    print()  # Add a blank line after each table
