from fastapi import APIRouter, HTTPException
from sqlalchemy import CursorResult, Inspector, MetaData, Table, inspect, text, Index
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker, DeclarativeBase
from sqlalchemy.ext.automap import automap_base
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Generator, List, Optional, Any, Type, Union, Set, Tuple
from enum import Enum
import logging
from datetime import datetime
from contextlib import contextmanager

# Utility functions for console output
gray = lambda x: f"\033[90m{x}\033[0m"
bold = lambda x: f"\033[1m{x}\033[0m"
green = lambda x: f"\033[32m{x}\033[0m"
yellow = lambda x: f"\033[33m{x}\033[0m"
red = lambda x: f"\033[31m{x}\033[0m"


class DBType(str, Enum):
    """Supported database types."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MSSQL = "mssql"  # Added support for Microsoft SQL Server

class DriverType(str, Enum):
    """Available driver types for database connections."""
    SYNC = "sync"
    ASYNC = "async"

class PoolConfig(BaseModel):
    """Database connection pool configuration."""
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_pre_ping: bool = True

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 1800,
                "pool_pre_ping": True
            }
        }
    )

class DBConfig(BaseModel):
    """Enhanced database configuration with connection pooling."""
    db_type: Union[DBType, str]
    driver_type: Union[DriverType, str]
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    database: str
    port: Optional[int] = None
    echo: bool = False
    pool_config: Optional[PoolConfig] = Field(default_factory=PoolConfig)
    schema_include: Optional[List[str]] = None  # Schemas to include
    schema_exclude: List[str] = Field(default=["information_schema", "pg_catalog"])
    ssl_mode: Optional[str] = None

    model_config = ConfigDict(use_enum_values=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.db_type = DBType(self.db_type) if isinstance(self.db_type, str) else self.db_type
        self.driver_type = DriverType(self.driver_type) if isinstance(self.driver_type, str) else self.driver_type

    @property
    def url(self) -> str:
        """Generate database URL based on configuration."""
        if self.db_type == DBType.SQLITE:
            return f"sqlite:///{self.database}"
        
        if self.db_type in (DBType.POSTGRESQL, DBType.MYSQL, DBType.MSSQL):
            if not all([self.user, self.password, self.host]):
                raise ValueError(f"Incomplete configuration for {self.db_type}")
            
            dialect = self.db_type.value
            driver = self._get_driver()
            
            port_str = f":{self.port}" if self.port is not None else ""
            ssl_str = f"?sslmode={self.ssl_mode}" if self.ssl_mode else ""
            
            return f"{dialect}{driver}://{self.user}:{self.password}@{self.host}{port_str}/{self.database}{ssl_str}"
        
        raise ValueError(f"Unsupported database type: {self.db_type}")

    def _get_driver(self) -> str:
        """Get appropriate database driver based on configuration."""
        if self.db_type == DBType.POSTGRESQL:
            return "+asyncpg" if self.driver_type == DriverType.ASYNC else "+psycopg2"
        elif self.db_type == DBType.MYSQL:
            return "+aiomysql" if self.driver_type == DriverType.ASYNC else "+pymysql"
        elif self.db_type == DBType.MSSQL:
            return "+pytds" if self.driver_type == DriverType.ASYNC else "+pyodbc"
        return ""


class DBForge(BaseModel):
    """Enhanced database management with extended functionality."""
    config: DBConfig = Field(...)
    engine: Engine = Field(default=None)
    metadata: MetaData = Field(default_factory=MetaData)
    Base: Type[DeclarativeBase] = Field(default_factory=automap_base)
    SessionLocal: sessionmaker = Field(default=None)
    view_names: Set[str] = Field(default_factory=set, description="Store view names")
    # _creation_time: datetime = Field(default_factory=datetime.now)
    inspector: Inspector = Field(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.engine = self._create_engine()
        self.inspector = inspect(self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        # self._test_connection()  # * Uncomment to test connection on initialization
        self._load_metadata()

    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with connection pooling."""
        pool_kwargs = self.config.pool_config.model_dump() if self.config.pool_config else {}
        return create_engine(
            self.config.url,
            echo=self.config.echo,  # ^ Uncomment for verbose logging
            **pool_kwargs
        )

    def _test_connection(self) -> None:
        """Test database connection and log connection info."""
        try:
            if self.config.db_type == DBType.SQLITE:
                print(f"{gray('Connected to SQLite database:')} {bold(self.config.database)}")
                return

            user, database = self.exec_raw_sql("SELECT current_user, current_database()").fetchone()
            print(f"\t{gray('Connected to')} {bold(database)} {gray('as')} {bold(user)}")
            print(f"\t{green('Database connection test successful!')}")

        except Exception as e:
            print(f"{red('Database connection test failed:')} {str(e)}")
            raise

    def _load_metadata(self) -> None:
        """Enhanced metadata loading with schema filtering and error handling."""
    
        def _get_filtered_schemas() -> List[str]:
            """Get filtered list of schemas based on configuration."""
            all_schemas = set(self.inspector.get_schema_names())
            excluded = set(self.config.schema_exclude)
            
            if self.config.schema_include:
                return sorted(set(self.config.schema_include) - excluded)
            return sorted(all_schemas - excluded)

        def _load_schema_objects(schema: str) -> None:
            """Load tables and views for a specific schema."""
            # Load views
            for view_name in self.inspector.get_view_names(schema=schema):
                full_name = f"{schema}.{view_name}" if schema else view_name
                self.view_names.add(full_name)
                Table(view_name, self.metadata, autoload_with=self.engine, schema=schema)

            # Load tables
            for table_name in self.inspector.get_table_names(schema=schema):
                full_name = f"{schema}.{table_name}" if schema else table_name
                if full_name not in self.view_names:  # * Skip if already loaded as a view
                    Table(table_name, self.metadata, autoload_with=self.engine, schema=schema)


        try:
            self.view_names.clear()
            [_load_schema_objects(schema) for schema in _get_filtered_schemas()]
            self.Base.prepare(self.engine, reflect=True)

        except Exception as e:
            print(f"{red('Error during metadata reflection:')} {str(e)}")
            raise

    # * PUBLIC METHODS (OPERATIONS)
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Context manager for database sessions."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_db(self) -> Generator[Session, None, None]:
        """Generator for database sessions (FastAPI dependency)."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def exec_raw_sql(self, query: str) -> CursorResult:
        """Execute raw SQL query."""
        with self.engine.connect() as connection: return connection.execute(text(query))

    def get_db_version(self) -> str:
        """Get database version information."""
        version_queries = {
            DBType.POSTGRESQL: "SELECT version()",
            DBType.MYSQL: "SELECT version()",
            DBType.SQLITE: "SELECT sqlite_version()",
            DBType.MSSQL: "SELECT @@VERSION"
        }

        query = version_queries.get(self.config.db_type)
        if query:
            result = self.exec_raw_sql(query).scalar()
            return str(result).split('\n')[0]  # First line of version info
        return "Unknown"

    def log_metadata_stats(self) -> None:
        """Log metadata statistics."""
        user, database = self.exec_raw_sql("SELECT current_user, current_database()").fetchone()

        print(f"{gray('Connected to')} {bold(database)} {gray('as')} {bold(user)}")
        print(f"{gray('Database version:')} {bold(self.get_db_version())}")
        
        if not self.metadata.tables:
            print(f"{yellow('No tables or views found in the database after reflection.')}")
            return

        total_views = len(self.view_names)
        print(f"Found {gray(f"{len(self.metadata.tables) - total_views}")} tables and {total_views} views")

        print(f"\n{bold('DB Connection Information:')}")
        print(f"\tType: {green(self.config.db_type)}")
        print(f"\tDriver: {green(self.config.driver_type)}")
        print(f"\tDatabase: {green(self.config.database)}")

        # Print object counts
        total_tables = len([t for t in self.metadata.tables.values()if t.name not in self.view_names])
        total_views = len(self.view_names)

        print(f"\n{bold('DB  Objects:')}")
        print(f"\tTables: {green(str(total_tables))}")
        print(f"\tViews: {green(str(total_views))}")

    def analyze_table_relationships(self) -> Dict[str, List[Dict[str, str]]]:
        """Analyze and return table relationships."""
        relationships = {}
        for table_name, table in self.metadata.tables.items():
            relationships[table_name] = []
            for fk in table.foreign_keys:
                relationships[table_name].append({
                    "from_col": fk.parent.name,
                    "to_table": fk.column.table.name,
                    "to_col": fk.column.name
                })
        return relationships


    # # * SOME USEFUL GET METHODS
    # # * GET METHODS
    # def get_table(self, table_name: str, schema: Optional[str] = None) -> Table:
    #     """Get a SQLAlchemy Table object."""
    #     full_name = f"{schema}.{table_name}" if schema else table_name
    #     if full_name not in self.metadata.tables:
    #         raise ValueError(f"Table {full_name} not found in the database")
    #     return self.metadata.tables[full_name]

    # def get_tables(self, schema: Optional[str] = None) -> Dict[str, Table]:
    #     """Get a dictionary of SQLAlchemy Table objects (excluding views)."""
    #     return {
    #         name: table
    #         for name, table in self.metadata.tables.items()
    #         if (schema is None or table.schema == schema) and not self.is_view(name)
    #     }

    # def get_views(self, schema: Optional[str] = None) -> Dict[str, Table]:
    #     """Get a dictionary of SQLAlchemy Table objects representing views."""
    #     return {
    #         name: view
    #         for name, view in self.metadata.tables.items()
    #         if (schema is None or view.schema == schema) and self.is_view(name)
    #     }

    # def get_all_tables(self) -> Dict[str, Table]:
    #     """Get all tables across all schemas (excluding views)."""
    #     return {name: table for name, table in self.metadata.tables.items() 
    #             if not self.is_view(name)}

    # def get_all_views(self) -> Dict[str, Table]:
    #     """Get all views across all schemas."""
    #     return {name: view for name, view in self.metadata.tables.items() 
    #             if self.is_view(name)}
