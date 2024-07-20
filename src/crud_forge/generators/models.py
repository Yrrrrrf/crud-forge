from typing import Dict, List, Tuple, Type, Any, Union
import sqlalchemy
from sqlalchemy.orm import declarative_base
from pydantic import BaseModel, create_model
from datetime import date, time, datetime

# Create base model for SQLAlchemy
Base = declarative_base()


class ModelGenerator:
    """
    Generates SQLAlchemy and Pydantic models from database metadata.

    This class provides methods to create SQLAlchemy and Pydantic models
    based on existing database tables or views.
    """
    SQL_TYPE_MAPPING = {
        'character varying': (sqlalchemy.String, str),
        'boolean': (sqlalchemy.Boolean, bool),
        'integer': (sqlalchemy.Integer, int),
        'numeric': (sqlalchemy.Numeric, float),
        'bigint': (sqlalchemy.BigInteger, int),
        'text': (sqlalchemy.Text, str),
        'varchar': (sqlalchemy.String, str),
        'date': (sqlalchemy.Date, date),
        'time': (sqlalchemy.Time, time),
        'timestamp': (sqlalchemy.DateTime, datetime),
        'datetime': (sqlalchemy.DateTime, datetime),
        'jsonb': (sqlalchemy.JSON, dict),
        'string_type': (sqlalchemy.String, str),
    }

    @classmethod
    def generate_sqlalchemy_model(
            cls,
            table_name: str,
            columns: List[Tuple[str, str]],
            primary_keys: List[str],
            schema: str
    ) -> Type[Base]:
        """
        Generate SQLAlchemy model class from table metadata.

        Args:
            table_name (str): Name of the table.
            columns (List[Tuple[str, str]]): List of column name and type pairs.
            primary_keys (List[str]): List of primary key column names.
            schema (str): Database schema name.

        Returns:
            Type[Base]: Generated SQLAlchemy model class.
        """
        attrs = {
            '__tablename__': table_name,
            '__table_args__': {'schema': schema}
        }

        print(f"\tSQLAlchemy Model: {table_name}")
        for column_name, column_type in columns:
            print(f"\t\tColumn: {column_name} - {column_type}")
            column_class, _ = cls.SQL_TYPE_MAPPING.get(column_type, (sqlalchemy.String, str))
            attrs[column_name] = sqlalchemy.Column(column_class, primary_key=column_name in primary_keys)

        return type(table_name.capitalize(), (Base,), attrs)

    @classmethod
    def generate_pydantic_model(
            cls,
            table_name: str,
            columns: List[Tuple[str, str]],
            schema: str = ''
    ) -> Type[BaseModel]:
        """
        Generate Pydantic model from table metadata.

        Args:
            table_name (str): Name of the table.
            columns (List[Tuple[str, str]]): List of column name and type pairs.
            schema (str, optional): Database schema name. Defaults to ''.

        Returns:
            Type[BaseModel]: Generated Pydantic model class.
        """
        fields: Dict[str, Any] = {}
        print(f"\tPydantic Model: {table_name}")
        for column_name, column_type in columns:
            print(f"\t\tColumn: {column_name} - {column_type}")
            _, pydantic_type = cls.SQL_TYPE_MAPPING.get(column_type, (str, str))
            fields[column_name] = (Union[pydantic_type, None], None)

        model_name = f"{table_name.capitalize()}Pydantic"
        if schema:
            model_name = f"{schema.capitalize()}{model_name}"

        return create_model(model_name, **fields)


class ViewModelGenerator(ModelGenerator):
    """
    Generates SQLAlchemy and Pydantic models for views.

    This class extends ModelGenerator to provide specific functionality
    for generating models based on database views.
    """

    @classmethod
    def generate_sqlalchemy_view_model(
            cls,
            table_name: str,
            columns: List[Tuple[str, str]],
            schema: str
    ) -> Type[Base]:
        """
        Generate SQLAlchemy model class for a view.

        Args:
            table_name (str): Name of the view.
            columns (List[Tuple[str, str]]): List of column name and type pairs.
            schema (str): Database schema name.

        Returns:
            Type[Base]: Generated SQLAlchemy model class for the view.
        """
        attrs = {
            '__tablename__': table_name,
            '__table_args__': {'schema': schema}
        }

        primary_keys = []
        print(f"\tSQLAlchemy Model: {table_name}")
        for column_name, column_type in columns:
            print(f"\t\tColumn: {column_name} - {column_type}")
            column_class, _ = cls.SQL_TYPE_MAPPING.get(column_type, str)
            column = sqlalchemy.Column(column_class)
            attrs[column_name] = column
            primary_keys.append(column)

        attrs['__mapper_args__'] = {'primary_key': primary_keys}

        return type(table_name.capitalize(), (Base,), attrs)


def generate_models(
        engine: sqlalchemy.Engine,
        schemas: List[str]
) -> Dict[str, Tuple[Type[Base], Type[BaseModel]]]:
    """
    Generate SQLAlchemy and Pydantic models for tables in specified schemas.

    Args:
        engine (Engine): SQLAlchemy engine instance.
        schemas (List[str]): List of schema names to generate models for.

    Returns:
        Dict[str, Tuple[Type[Base], Type[BaseModel]]]: Dictionary of generated models.
    """
    combined_models = {}
    metadata = sqlalchemy.MetaData()

    for schema in schemas:
        metadata.reflect(bind=engine, schema=schema, extend_existing=True)

        for table_name, table in metadata.tables.items():
            if table.schema == schema:
                table_name = table_name.split('.')[-1]
                columns = [(col.name, col.type.__class__.__name__.lower()) for col in table.columns]
                primary_keys = [col.name for col in table.columns if col.primary_key]
                sqlalchemy_model = ModelGenerator.generate_sqlalchemy_model(table_name, columns, primary_keys, schema)
                pydantic_model = ModelGenerator.generate_pydantic_model(table_name, columns, schema)
                combined_models[table_name] = (sqlalchemy_model, pydantic_model)

    return combined_models


def generate_views(
        engine: sqlalchemy.Engine,
        schemas: List[str]
) -> Dict[str, Tuple[Type[Base], Type[BaseModel]]]:
    """
    Generate SQLAlchemy and Pydantic models for views in specified schemas.

    Args:
        engine (Engine): SQLAlchemy engine instance.
        schemas (List[str]): List of schema names to generate view models for.

    Returns:
        Dict[str, Tuple[Type[Base], Type[BaseModel]]]: Dictionary of generated view models.
    """
    combined_models = {}
    metadata = sqlalchemy.MetaData()
    metadata.reflect(bind=engine, views=True, extend_existing=True)

    for schema in schemas:
        for table_name, table in metadata.tables.items():
            # todo: refactor this to use a regex pattern...
            if table_name.startswith('report_') or table_name.startswith('view_'):
                table_name = table_name.split('.')[-1]
                columns = [(col.name, col.type.__class__.__name__.lower()) for col in table.columns]
                sqlalchemy_model = ViewModelGenerator.generate_sqlalchemy_view_model(table_name, columns, schema)
                pydantic_model = ViewModelGenerator.generate_pydantic_model(table_name, columns, schema)
                combined_models[table_name] = (sqlalchemy_model, pydantic_model)

    return combined_models
