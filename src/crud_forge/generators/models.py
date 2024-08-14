from typing import Dict, List, Tuple, Type, Any, Union
from crud_forge.db import SchemaMetadata, ColumnMetadata
import sqlalchemy
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel, create_model
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
        'varchar': (sqlalchemy.String, str),
        'uuid': (sqlalchemy.String, UUID),
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

        print(f"\tSQLAlchemy Model: {table_name}")
        for column in columns:
            print(f"\t\tColumn: {column.name} - {column.type} {'- PK' if column.is_primary_key else ''}")
            column_class, _ = cls.SQL_TYPE_MAPPING.get(column.type, (sqlalchemy.String, str))
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
        print(f"\tPydantic Model: {table_name}")
        for column in columns:
            print(f"\t\tColumn: {column.name} - {column.type}")
            _, pydantic_type = cls.SQL_TYPE_MAPPING.get(column.type, (str, str))
            fields[column.name] = (Union[pydantic_type, None], None)

        model_name = f"{table_name.capitalize()}_Pydantic"
        if schema: model_name = f"{schema.capitalize()}_{model_name}"

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
        print(f"Generating models for schema: {schema_name}")
        schema_models: Dict[str, Tuple[Type[Base], Type[BaseModel]]] = {}

        for table_name, table_metadata in schema_metadata.tables.items():
            print(f"Table: {table_name}")
            columns = table_metadata.columns
            sqlalchemy_model = ModelGenerator.generate_sqlalchemy_model(table_name, columns, schema_name)
            pydantic_model = ModelGenerator.generate_pydantic_model(table_name, columns, schema_name)
            schema_models[table_name] = (sqlalchemy_model, pydantic_model)

        combined_models[schema_name] = schema_models

    return combined_models

# Usage example:
# from your_db_manager import DatabaseManager
# db_manager = DatabaseManager(db_url="your_db_url")
# metadata = db_manager.metadata
# models = generate_models_from_metadata(metadata)