from fastapi import APIRouter, HTTPException
from sqlalchemy import CursorResult, MetaData, Table, inspect, text
from sqlalchemy.engine import Engine, create_engine
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.automap import automap_base
from typing import Dict, Generator, List, Optional, Any, Type, Union
from enum import Enum
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

gray = lambda x: f"\033[90m{x}\033[0m"
bold = lambda x: f"\033[1m{x}\033[0m"


class DBType(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"

class DriverType(str, Enum):
    SYNC = "sync"
    ASYNC = "async"

class DBConfig(BaseModel):
    db_type: Union[DBType, str]
    driver_type: Union[DriverType, str]
    user: Optional[str] = None
    password: Optional[str] = None
    host: Optional[str] = None
    database: str
    port: Optional[int] = None
    echo: bool = False

    model_config = ConfigDict(use_enum_values=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.db_type = DBType(self.db_type) if isinstance(self.db_type, str) else self.db_type
        self.driver_type = DriverType(self.driver_type) if isinstance(self.driver_type, str) else self.driver_type

    @property
    def url(self) -> str:
        if self.db_type == DBType.SQLITE:
            return f"sqlite:///{self.database}"
        elif self.db_type in (DBType.POSTGRESQL, DBType.MYSQL):
            if not all([self.user, self.password, self.host]):
                raise ValueError(f"Incomplete configuration for {self.db_type}")
            
            dialect = self.db_type.value
            driver = "+asyncpg" if self.driver_type == DriverType.ASYNC else "+psycopg2" if self.db_type == DBType.POSTGRESQL else \
                     "+aiomysql" if self.driver_type == DriverType.ASYNC else "+pymysql"

            port_str = f":{self.port}" if self.port is not None else ""
            return f"{dialect}{driver}://{self.user}:{self.password}@{self.host}{port_str}/{self.database}"
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")


class DBForge(BaseModel):
    config: DBConfig = Field(...)
    engine: Engine = Field(default=None)
    metadata: MetaData = Field(default_factory=MetaData)
    Base: Any = Field(default_factory=automap_base)
    SessionLocal: sessionmaker = Field(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        self.engine = create_engine(self.config.url, echo=self.config.echo)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self._test_connection()
        self._load_metadata()
        # todo: Add support for views & enums
        # ^ Views are not reflected by default (this means that they are not available in the metadata)
        # self.metadata.reflect(self.engine, views=True)
        # ^ By adding the views=True parameter, we can reflect views as well
        # ^ This will allow us to access the view objects in the metadata
        # ^ To access a view object, use self.metadata.tables['view_name']
        # ^ The only way to differentiate between tables and views is by checking the .is_view attribute
        # ^ So, to check if a table is a view, use self.metadata.tables['view_name'].is_view

    def _test_connection(self):
        try:
            user, database = self.exec_raw_sql("SELECT current_user, current_database()").fetchone()
            logger.info(f" {gray('Connected to')} {bold(database)} {gray('as')} {bold(user)}")
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")

    def _load_metadata(self) -> None:
        try:
            inspector = inspect(self.engine)
            for schema in inspector.get_schema_names():
                if schema in ['information_schema', 'pg_catalog']:
                    continue
                logger.info(f"[Schema] {gray(schema)}")

                for table in inspector.get_table_names(schema=schema):
                    Table(table, self.metadata, autoload_with=self.engine, schema=schema)

            self.Base.prepare(self.engine, reflect=True)

            if not self.metadata.tables:
                logger.warning("No tables found in the database after reflection.")
            else:
                logger.info(f" {gray('Metadata loaded successfully')}")
                logger.info(f"Found {len(inspector.get_schema_names()) - 1} schemas")
                logger.info(f"Found {len(self.metadata.tables)} tables")

        except Exception as e:
            logger.error(f"Error during metadata reflection: {str(e)}")

    def exec_raw_sql(self, query: str) -> CursorResult:
        with self.engine.connect() as connection:
            return connection.execute(text(query))

    def get_db(self) -> Generator[Session, None, None]:
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()


    # * GET METHODS

    def get_table(self, table_name: str, schema: Optional[str] = None) -> Table:
        """Get a SQLAlchemy Table object."""
        full_name = f"{schema}.{table_name}" if schema else table_name
        if full_name not in self.metadata.tables:
            raise ValueError(f"Table {full_name} not found in the database")
        return self.metadata.tables[full_name]

    def get_view(self, view_name: str, schema: Optional[str] = None) -> Table:
        """Get a SQLAlchemy Table object representing a view."""
        full_name = f"{schema}.{view_name}" if schema else view_name
        if full_name not in self.metadata.tables or not self.metadata.tables[full_name].is_view:
            raise ValueError(f"View {full_name} not found in the database")
        return self.metadata.tables[full_name]

    def get_tables(self, schema: Optional[str] = None) -> Dict[str, Table]:
        """Get a dictionary of SQLAlchemy Table objects (excluding views)."""
        return {
            table_name: table
            for table_name, table in self.metadata.tables.items()
            if (schema is None or table.schema == schema) and not table.is_view
        }

    def get_views(self, schema: Optional[str] = None) -> Dict[str, Table]:
        """Get a dictionary of SQLAlchemy Table objects representing views."""
        return {
            view_name: view
            for view_name, view in self.metadata.tables.items()
            if (schema is None or view.schema == schema) and view.is_view
        }

    def get_all_tables(self) -> Dict[str, Table]:
        """Get all tables across all schemas (excluding views)."""
        return {name: table for name, table in self.metadata.tables.items() if not table.is_view}

    def get_all_views(self) -> Dict[str, Table]:
        """Get all views across all schemas."""
        return {name: view for name, view in self.metadata.tables.items() if view.is_view}
