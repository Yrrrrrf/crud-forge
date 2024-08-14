from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any
from sqlalchemy import create_engine, Engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from functools import lru_cache

@dataclass
class DBConfig:
    db_type: str  # database type (sqlite, postgresql, mysql)
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    database: Optional[str] = None
    port: Optional[int] = None

    def __post_init__(self):
        """Initialize the DBConfig with default values for port and host based on the database type."""
        # * list of ['db_type', default_port, default_host]
        db_configs: List[Tuple[str, Optional[int], Optional[str]]] = [
            ('sqlite', None, None),
            ('postgresql', 5432, 'localhost'),
            ('mysql', 3306, 'localhost'),
            # * Add new database types here in the future
        ]

        for db, default_port, default_host in db_configs:
            if self.db_type == db:  # * if the db_type matches the current db
                match (self.port, self.host):  # * match the port and host
                    case (None, None): self.port, self.host = default_port, default_host
                    case (None, _): self.port = default_port
                    case (_, None): self.host = default_host
                break
        else: raise ValueError(f"Unsupported database type: {self.db_type}")
        if not self.database: raise ValueError("Database name must be provided")

    @property
    def url(self) -> str:
        match self.db_type:
            case 'sqlite': return f"{self.db_type}:///{self.database}"
            case 'postgresql' | 'mysql':
                if not all([self.user, self.password, self.host]):
                    raise ValueError(f"Incomplete configuration for {self.db_type}")
                return f"{self.db_type}://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
            case _: raise ValueError(f"Unsupported database type: {self.db_type}")

@dataclass
class TableMetadata:
    name: str  # table name
    # columns as a list of tuples (column_name, column_type)
    columns: List[Tuple[str, str]] = field(default_factory=list)

@dataclass
class SchemaMetadata:
    name: str  # schema name
    # tables as a dictionary of table_name: TableMetadata
    tables: Dict[str, TableMetadata] = field(default_factory=dict)


class DatabaseManager:
    """Manages database connection, session creation, and metadata retrieval."""

    def __init__(self, db_url: Optional[str] = None, **kwargs):
        """Initialize the DatabaseManager."""
        try:
            self.db_config = self._create_db_config(db_url, **kwargs)
            self.engine: Engine = create_engine(self.db_config.url)
            self.SessionLocal: sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.metadata: Dict[str, SchemaMetadata] = self._get_metadata()
        except Exception as e:
            print(f"Error initializing DatabaseManager: {str(e)}")
            raise

    @staticmethod
    def _create_db_config(db_url: Optional[str], **kwargs) -> DBConfig:
        if db_url:
            parts = db_url.split('://')
            if len(parts) != 2:
                raise ValueError("Invalid database URL format")
            db_type = parts[0]
            rest = parts[1].split('@')
            if len(rest) == 2:
                user_pass, host_port_db = rest
                user, password = user_pass.split(':')
                host_port, database = host_port_db.split('/')
                if ':' in host_port:
                    host, port = host_port.split(':')
                    return DBConfig(db_type=db_type, user=user, password=password, host=host, port=int(port), database=database)
                else:
                    return DBConfig(db_type=db_type, user=user, password=password, host=host_port, database=database)
            else:
                raise ValueError("Invalid database URL format")
        elif all(key in kwargs for key in ['db_type', 'user', 'password', 'host', 'database']):
            return DBConfig(**kwargs)
        else:
            raise ValueError("Insufficient database configuration provided")

    def get_db(self) -> Session:
        """Provide a database session."""
        db: Session = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def test_connection(self) -> bool:
        """Test the database connection."""
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Connection test successful")
            return True
        except SQLAlchemyError as e:
            print(f"Connection test failed: {str(e)}")
            return False

    @lru_cache(maxsize=None)
    def _get_metadata(self) -> Dict[str, SchemaMetadata]:
        """Retrieve all metadata including schemas, tables, and columns."""
        inspector = inspect(self.engine)
        metadata: Dict[str, SchemaMetadata] = {}

        match self.db_config.db_type:
            case 'postgresql':
                schemas = [schema for schema in inspector.get_schema_names() 
                           if schema not in ('information_schema', 'pg_catalog')]
            case 'mysql' | 'sqlite': schemas = ['default']
            case _: schemas = inspector.get_schema_names()

        for schema in schemas:
            schema_metadata = SchemaMetadata(name=schema)
            
            for table in inspector.get_table_names(schema=schema if schema != 'default' else None):
                schema_metadata.tables[table] = TableMetadata(name=table, columns=self._get_table_columns(inspector, schema, table))
            # # * same as above but using some list comprehension
            # schema_metadata.tables = {table: TableMetadata(name=table, columns=self._get_table_columns(inspector, schema, table)) for table in tables}

            metadata[schema] = schema_metadata

        return metadata

    @staticmethod
    def _get_table_columns(inspector: Any, schema: str, table: str) -> List[Tuple[str, str]]:
        """Get the columns of a specific table."""
        columns = inspector.get_columns(table, schema=None if schema == 'default' else schema)
        return [(col['name'], str(col['type'])) for col in columns]

    @property
    def schemas(self) -> List[str]:
        """Get the list of schemas."""
        return list(self.metadata.keys())

    @property
    def tables(self) -> Dict[str, List[str]]:
        """Get the dictionary of tables for each schema."""
        return {schema: list(self.metadata[schema].tables.keys()) for schema in self.schemas}

    def get_table_columns(self, schema: str, table: str) -> List[Tuple[str, str]]:
        """Get the columns of a specific table."""
        return self.metadata[schema].tables[table].columns

# Example usage:
# db_manager = DatabaseManager(db_url="postgresql://user:pass@localhost/db")
# print(db_manager.schemas)
# print(db_manager.tables)
# print(db_manager.get_table_columns('public', 'users'))