from typing import Dict, List, Tuple, Type, Any, Union
from crud_forge.db import SchemaMetadata, ColumnMetadata, TableMetadata
import sqlalchemy
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel, create_model, Field
from datetime import date, time, datetime
from uuid import UUID

# Create base model for SQLAlchemy
Base = declarative_base()

class ModelGenerator:
    """
    Generates SQLAlchemy and Pydantic models from database metadata.
    """
    SQL_TYPE_MAPPING = {
        'character varying': (sqlalchemy.String, str),
        'string_type': (sqlalchemy.String, str),
        'varchar': (sqlalchemy.VARCHAR, str),
        'uuid': (sqlalchemy.UUID, UUID),
        'text': (sqlalchemy.Text, str),
        'boolean': (sqlalchemy.Boolean, bool),
        'integer': (sqlalchemy.Integer, int),
        'bigint': (sqlalchemy.BigInteger, int),
        'numeric': (sqlalchemy.Numeric, float),
        'date': (sqlalchemy.Date, date),
        'time': (sqlalchemy.Time, time),
        'timestamp': (sqlalchemy.DateTime, datetime),
        'datetime': (sqlalchemy.DateTime, datetime),
        'jsonb': (sqlalchemy.JSON, dict),
    }

    @staticmethod
    def print_model_field(table: TableMetadata):
        for column in table.columns:
            # * PRINT ON THE FORM OF:
            # * - [PK] for primary key (in green) (only one primary key per table)
            # * - [FK] for foreign key (in cyan) (can have multiple foreign keys per table)
            # * - <field_name> in bold (some alignment)
            # * - <field_type> in gray italic (alignment to the right)
            is_pk = '\033[92m[PK]\033[0m' if column.is_primary_key else ''  # green
            is_fk = '\033[96m[FK]\033[0m' if column.is_foreign_key else ''  # cyan

            match (column.is_primary_key, column.is_foreign_key) :
                case (True, False): pre_str = f"{is_pk}\t"
                case (False, True): pre_str = f"{is_fk}\t"
                case (True, True): pre_str = f"{is_pk}{is_fk}"
                case (False, False): pre_str = '\t'

            field_name = column.name
            field_type = f"\033[3m\033[90m{column.type}\033[0m"  # italic + gray
            print(f"\t\t{pre_str}{field_name:<32} {field_type:<20}")
    
    @classmethod
    def generate_sqlalchemy_model(
            cls,
            table_name: str,
            columns: List[ColumnMetadata],
            schema: str
    ) -> Type[Base]:
        """
        Generate SQLAlchemy model class from table metadata.
        """
        attrs = {
            '__tablename__': table_name,
            '__table_args__': {'schema': schema}
        }

        print(f"\t  \033[94m[SQLAlchemy]\033[0m {table_name}")

        for column in columns:
            column_class, _ = cls.SQL_TYPE_MAPPING.get(column.type.lower(), (sqlalchemy.String, str))
            attrs[column.name] = sqlalchemy.Column(column_class, primary_key=column.is_primary_key)

        return type(table_name.capitalize(), (Base,), attrs)

    @classmethod
    def generate_pydantic_model(
            cls,
            table_name: str,
            columns: List[ColumnMetadata],
            schema: str = ''
    ) -> Type[BaseModel]:
        """
        Generate Pydantic model from table metadata.
        """
        fields: Dict[str, Any] = {}

        model_name = f"{table_name}_pydantic"
        print(f"\t  \033[95m[ Pydantic ]\033[0m {model_name}")

        for column in columns:
            _, pydantic_type = cls.SQL_TYPE_MAPPING.get(column.type.lower(), (str, str))
            fields[column.name] = (Union[pydantic_type, None], Field(default=None))

        return create_model(model_name, **fields)

def generate_models_from_metadata(metadata: Dict[str, SchemaMetadata]) -> Dict[str, Dict[str, Tuple[Type[Base], Type[BaseModel]]]]:
    """
    Generate SQLAlchemy and Pydantic models from DatabaseManager metadata.

    Args:
        metadata (Dict[str, SchemaMetadata]): Metadata from DatabaseManager.

    Returns:
        Dict[str, Dict[str, Tuple[Type[Base], Type[BaseModel]]]]: Dictionary of generated models.
    """
    combined_models = {}

    for schema_name, schema_metadata in metadata.items():
        print(f"\n\033[93m[Schema]\033[0m {schema_name}")
        schema_models: Dict[str, Tuple[Type[Base], Type[BaseModel]]] = {}

        for table_name, table_metadata in schema_metadata.tables.items():
            print(f"\n\t\033[96m[Table]\033[0m \033[1m{table_name}\033[0m")
            sqlalchemy_model = ModelGenerator.generate_sqlalchemy_model(table_name, table_metadata.columns, schema_name)
            pydantic_model = ModelGenerator.generate_pydantic_model(table_name, table_metadata.columns, schema_name)
            ModelGenerator.print_model_field(table_metadata)
            schema_models[table_name] = (sqlalchemy_model, pydantic_model)
            
        combined_models[schema_name] = schema_models

    return combined_models

# Usage example:
# from your_db_manager import DatabaseManager
# db_manager = DatabaseManager(db_url="your_db_url")
# metadata = db_manager.metadata
# models = generate_models_from_metadata(metadata)

    