"""Main file for testing the new DBForge implementation"""
from fastapi import FastAPI, APIRouter
from sqlalchemy import text
from typing import Dict, Any
import logging
import os

# Import our new enhanced DBForge and related classes
from forge.model import ModelForge
from forge.db import DBForge, DBConfig, DBType, DriverType, PoolConfig
from forge.utils import AppConfig, allow_all_middleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI()
allow_all_middleware(app)

# Initialize configuration
app_config = AppConfig(
    PROJECT_NAME="Database Test",
    VERSION="0.1.0",
    DESCRIPTION="Testing the new DBForge implementation",
    AUTHOR="Test User",
)
app_config.set_app_data(app)
app_config.setup_logging()

# * Initialize DBForge & DBConfig
db_manager: DBForge = DBForge(config=DBConfig(
    db_type=os.getenv('DB_TYPE', 'postgresql'),
    driver_type=os.getenv('DRIVER_TYPE', 'sync'),
    database=os.getenv('DB_NAME', 'pharmacy_management'),
    user=os.getenv('DB_USER', 'pharmacy_management_owner'),
    password=os.getenv('DB_PASSWORD', 'secure_pharmacy_pwd'),
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', 5432),
    echo=True,
    pool_config=PoolConfig(
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_pre_ping=True
    ),
))

test_router = APIRouter(prefix="/test", tags=["Tests"])

@test_router.get("/connection")
async def test_connection() -> Dict[str, Any]:
    """Test database connection and return basic information."""
    try:       
        with db_manager.get_session() as session:
            # Get user permissions
            if db_manager.config.db_type == DBType.POSTGRESQL:
                result = session.execute(text("SELECT current_user, session_user, current_database()"))
                current_user, session_user, current_db = result.fetchone()
            else:
                current_user = session_user = "N/A"
                current_db = db_manager.config.database

        # Get table statistics
        table_stats = db_manager.get_table_stats()
        
        # Analyze relationships
        relationships = db_manager.analyze_table_relationships()

        return {
            "status": "connected",
            "database_version": db_manager.get_db_version(),
            "current_user": current_user,
            "session_user": session_user,
            "current_database": current_db,
            "table_count": len(table_stats),
            "view_count": len(db_manager.view_names),
            "relations": relationships
        }
    except Exception as e:
        print(f"\033[91mConnection test failed: {str(e)}\033[0m")
        return {
            "status": "error",
            "error": str(e)
        }

@test_router.get("/schemas/{schema}/tables")
async def get_schema_tables(schema: str) -> Dict[str, Any]:
    """Get detailed information about tables in a specific schema."""
    try:
        tables = db_manager.get_table_stats(schema=schema)
        
        # If PostgreSQL, get schema size
        return {
            "schema": schema,
            "tables": tables,
        }
    except Exception as e:
        print(f"\033[91mFailed to get schema information: {str(e)}\033[0m")
        return {
            "status": "error",
            "error": str(e)
        }

app.include_router(test_router)  # Include the test router


# * Startup event
def on_startup():
    print("\n\n\033[92mStartup completed successfully!\033[0m\n\n")

    print(f"\tType: {db_manager.config.db_type}")
    print(f"\tDriver: {db_manager.config.driver_type}")
    print(f"\t\tTables [{len(db_manager.metadata.tables):>3}]")
    print(f"\t\tViews  [{len(db_manager.view_names):>3}]")


on_startup()  # Run the startup event


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
