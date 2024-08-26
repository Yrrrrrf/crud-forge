from datetime import date, time, datetime
from enum import Enum
from typing import Dict, Tuple, Type, Union
from uuid import UUID
import sqlalchemy
from sqlalchemy import Enum as SQLAlchemyEnum

# Custom type for representing enum types
EnumType = Union[Type[Enum], Type[SQLAlchemyEnum]]

# * Mapping of SQL types to Python types
SQL_TYPE_MAPPING: Dict[str, Tuple[Type, Type]] = {
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

def update_type_mapping(enum_types: Dict[str, Dict[str, EnumType]]):
    """
    Update SQL_TYPE_MAPPING with enum types from the database.
    
    Args:
        enum_types: Dictionary of enum types, keyed by schema and enum name.
    """
    for schema, enums in enum_types.items():
        for enum_name, (sqlalchemy_enum, python_enum) in enums.items():
            type_key = f"{schema}.{enum_name}"
            SQL_TYPE_MAPPING[type_key] = (sqlalchemy_enum, python_enum)
