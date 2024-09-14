
# SQL_TYPE_MAPPING: Dict[str, Tuple[Type, Type]] = {
#     r'uuid': (sqlalchemy.UUID, UUID),  # * Universally Unique IDentifier
 
#     # * String types
#     r'varchar(\(\d+\))?': (sqlalchemy.String, str),
#     r'character\s+varying(\(\d+\))?': (sqlalchemy.String, str),
#     r'text': (sqlalchemy.Text, str),
#     r'char(\(\d+\))?': (sqlalchemy.CHAR, str),

#     # * Numeric types
#     r'integer': (sqlalchemy.Integer, int),
#     r'bigint': (sqlalchemy.BigInteger, int),
#     r'smallint': (sqlalchemy.SmallInteger, int),
#     r'decimal(\(\d+,\s*\d+\))?': (sqlalchemy.DECIMAL, Decimal),
#     r'numeric(\(\d+,\s*\d+\))?': (sqlalchemy.DECIMAL, Decimal),
#     r'real': (sqlalchemy.Float, float),
#     r'double\s+precision': (sqlalchemy.Float, float),

#     # * Discrete types
#     r'bit': (sqlalchemy.Boolean, bool),
#     r'bytea': (sqlalchemy.LargeBinary, bytes),
#     r'boolean': (sqlalchemy.Boolean, bool),

#     # * Date and Time types
#     r'date': (sqlalchemy.Date, date),
#     r'time(\(\d+\))?': (sqlalchemy.Time, time),
#     r'timestamp(\(\d+\))?(\s+with(out)?\s+time\s+zone)?': (sqlalchemy.DateTime, datetime),
#     r'interval': (sqlalchemy.Interval, timedelta),

#     # * JSON types
#     r'json': (sqlalchemy.JSON, dict),
#     r'jsonb': (sqlalchemy.JSON, dict),

#     # * Enum type (generic match, specific enums should be handled separately)
#     r'enum': (sqlalchemy.Enum, str),

#     # Array types
#     r'(\w+)\[\]': (sqlalchemy.ARRAY, list),
    
#     # # * Network address types
#     # r'inet': (sqlalchemy.dialects.postgresql.INET, str),
#     # r'cidr': (sqlalchemy.dialects.postgresql.CIDR, str),
#     # r'macaddr': (sqlalchemy.dialects.postgresql.MACADDR, str),
    
#     # # * Geometric types
#     # r'point': (sqlalchemy.dialects.postgresql.POINT, tuple),
#     # r'line': (sqlalchemy.dialects.postgresql.LINE, str),
#     # r'lseg': (sqlalchemy.dialects.postgresql.LSEG, tuple),
#     # r'box': (sqlalchemy.dialects.postgresql.BOX, tuple),
#     # r'path': (sqlalchemy.dialects.postgresql.PATH, list),
#     # r'polygon': (sqlalchemy.dialects.postgresql.POLYGON, list),
#     # r'circle': (sqlalchemy.dialects.postgresql.CIRCLE, tuple),
    
#     # # * Full text search types
#     # r'tsvector': (sqlalchemy.dialects.postgresql.TSVECTOR, str),
#     # r'tsquery': (sqlalchemy.dialects.postgresql.TSQUERY, str),
    
#     # # * Range types
#     # r'int4range': (sqlalchemy.dialects.postgresql.INT4RANGE, range),
#     # r'int8range': (sqlalchemy.dialects.postgresql.INT8RANGE, range),
#     # r'numrange': (sqlalchemy.dialects.postgresql.NUMRANGE, range),
#     # r'tsrange': (sqlalchemy.dialects.postgresql.TSRANGE, range),
#     # r'tstzrange': (sqlalchemy.dialects.postgresql.TSTZRANGE, range),
#     # r'daterange': (sqlalchemy.dialects.postgresql.DATERANGE, range),
# }

# todo: Add some more types using regex & the SQLAlchemy types...
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import re
from typing import Any, Dict, Type
from uuid import UUID


SQL_TYPE_MAPPING: Dict[str, Type] = {
    r'uuid': UUID,
    r'varchar(\(\d+\))?': str,
    r'character\s+varying(\(\d+\))?': str,
    r'text': str,
    r'char(\(\d+\))?': str,
    r'integer': int,
    r'bigint': int,
    r'smallint': int,
    r'decimal(\(\d+,\s*\d+\))?': Decimal,
    r'numeric(\(\d+,\s*\d+\))?': Decimal,
    r'real': float,
    r'double\s+precision': float,
    r'bit': bool,
    r'bytea': bytes,
    r'boolean': bool,
    r'date': date,
    r'time(\(\d+\))?': time,
    r'timestamp(\(\d+\))?(\s+with(out)?\s+time\s+zone)?': datetime,
    r'interval': timedelta,
    r'json': dict,
    r'jsonb': dict,
    r'enum': str,
    r'(\w+)\[\]': list,
}

def get_eq_type(sql_type: str) -> Type:
    """Map SQLAlchemy types to Python types using regex matching."""
    sql_type_lower = sql_type.lower()
    for pattern, py_type in SQL_TYPE_MAPPING.items():
        if re.match(pattern, sql_type_lower):
            return py_type
    return Any  # Default fallback
