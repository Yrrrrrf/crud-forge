from typing import Dict, List, Tuple, Type, Any, Union
from sqlalchemy.orm import declarative_base
import sqlalchemy
import pydantic

# ? self-imports
from crud_forge.db import DatabaseManager, SchemaMetadata, ColumnMetadata, TableMetadata
from crud_forge.generators import SQL_TYPE_MAPPING  # types mapping for SQLAlchemy and Pydantic models


# Create base model for SQLAlchemy
Base = declarative_base()

class ModelGenerator:
    """
    Generates SQLAlchemy and Pydantic models from database metadata.
    """
    @staticmethod
    def print_model_field(table: TableMetadata):
        for column in table.columns:
            is_pk = '\033[92m[PK]\033[0m'  # green
            is_fk = '\033[96m[FK]\033[0m'  # cyan

            match (column.is_primary_key, column.is_foreign_key, column.is_enum):
                case (False, False, False): pre_str = '\t'  # no flag
                case (False,  True, False): pre_str = f"{is_fk}\t"  # only fk
                case ( True, False, False): pre_str = f"{is_pk}\t"  # only pk
                case ( True,  True, False): pre_str = f"{is_pk}{is_fk}"  # pk + fk
                case (    _,     _,  True): pre_str = "\033[93m[ENUM]\033[0m\t"  # enum flag (yellow)
                case _: raise ValueError("'UNREACHABLE!'. IF YOU SEE THIS IT MEANS I'M DUMB .____.")

            field_type = f"\033[3m\033[90m{column.type}\033[0m" + (" (Enum)" if column.is_enum else "")

            print(f"\t\t{pre_str}{column.name:<32} {field_type:<20}")


    @classmethod
    def gen_sqlalchemy_model(
            cls,
            table_name: str,
            columns: List[ColumnMetadata],
            schema: str
    ) -> Type[Base]:  # type: ignore
        """
        Generate SQLAlchemy model class from table metadata.
        """
        attrs = {
            '__tablename__': table_name,
            '__table_args__': {'schema': schema}
        }

        print(f"\t    \033[94m[SQLAlchemy]_Model:\033[0m {table_name}")

        for column in columns:
            column_class, _ = SQL_TYPE_MAPPING.get(column.type.lower(), (sqlalchemy.String, str))
            attrs[column.name] = sqlalchemy.Column(column_class, primary_key=column.is_primary_key)

        return type(table_name.capitalize(), (Base,), attrs)

    @classmethod
    def gen_pydantic_model(
            cls,
            table_name: str,
            columns: List[ColumnMetadata],
            schema: str = ''
    ) -> Type[pydantic.BaseModel]:
        """
        Generate Pydantic model from table metadata.
        """
        fields: Dict[str, Any] = {}

        model_name = f"{table_name}_pydantic"
        print(f"\t    \033[95m[ Pydantic ]_Model:\033[0m {model_name}")

        for column in columns:
            _, pydantic_type = SQL_TYPE_MAPPING.get(column.type.lower(), (str, str))
            fields[column.name] = (Union[pydantic_type, None], pydantic.Field(default=None))

        return pydantic.create_model(model_name, **fields)

def from_metadata(
    db_manager: DatabaseManager
) -> Dict[str, Dict[str, Tuple[Type[Base], Type[pydantic.BaseModel]]]]:  # type: ignore
    """
    Generate SQLAlchemy and Pydantic models from DatabaseManager metadata.

    Args:
        metadata (Dict[str, SchemaMetadata]): Metadata from DatabaseManager.

    Returns:
        Dict[str, Dict[str, Tuple[Type[Base], Type[BaseModel]]]]: Dictionary of generated models.
    """
    combined_models: Dict[str, Dict[str, Tuple[Type[Base], Type[pydantic.BaseModel]]]] = {}  # type: ignore

    for schema_name, schema_metadata in db_manager.metadata.items():
        print(f"\n\033[93m[Schema]\033[0m {schema_name}")
        schema_models: Dict[str, Tuple[Type[Base], Type[pydantic.BaseModel]]] = {}  # type: ignore

        for table_name, table_metadata in schema_metadata.tables.items():
            print(f"\n\t\033[96m[Table]\033[0m \033[1m{schema_name}.\033[4m{table_name}\033[0m")
            [sqlalchemy_model, pydantic_model] = map(
                lambda func: func(table_name, table_metadata.columns, schema_name),
                [ModelGenerator.gen_sqlalchemy_model, ModelGenerator.gen_pydantic_model]
            )
            ModelGenerator.print_model_field(table_metadata)
            schema_models[table_name] = (sqlalchemy_model, pydantic_model)
            
        combined_models[schema_name] = schema_models

    return combined_models
