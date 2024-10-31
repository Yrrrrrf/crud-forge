"""Main file for showcasing the database structure using DBForge"""
from fastapi import FastAPI, APIRouter
from sqlalchemy import Table, Enum as SQLAlchemyEnum
from typing import Dict, List, Any, Optional
import os

# Import our enhanced DBForge and related classes
from forge.api import APIConfig, APIForge
from forge.db import DBForge, DBConfig, DBType, DriverType, PoolConfig
from forge.model import ModelForge
from forge.utils import *
from forge import init_app

init_app()
# Initialize FastAPI
app = FastAPI()
allow_all_middleware(app)

# Initialize configuration
app_config = AppConfig(
    PROJECT_NAME="Database Inspector",
    VERSION="0.2.0",
    DESCRIPTION="Enhanced database structure visualization",
    AUTHOR="Database Inspector",
)
app_config.set_app_data(app)

# Initialize DBForge with configuration
db_manager = DBForge(config=DBConfig(
    db_type=os.getenv('DB_TYPE', 'postgresql'),
    driver_type=os.getenv('DRIVER_TYPE', 'sync'),
    database=os.getenv('DB_NAME', 'pharmacy_management'),
    user=os.getenv('DB_USER', 'pharmacy_management_owner'),
    password=os.getenv('DB_PASSWORD', 'secure_pharmacy_pwd'),
    host=os.getenv('DB_HOST', 'localhost'),
    port=os.getenv('DB_PORT', 5432),
    echo=False,
    pool_config=PoolConfig(
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_pre_ping=True
    ),
))
db_manager.log_metadata_stats()
# db_manager._test_connection()

model_forge: ModelForge = ModelForge(db_manager=db_manager)
# model_forge.log_schema_structure()

# * Print the models
# [print(f"{bold('Models')} {table}") for table in model_forge.models.keys()]
# [print(f"{bold('PyEnum:')} {table}") for table in model_forge.enum_cache.values()]

api_forge = APIForge(model_forge=model_forge, config=APIConfig(
    include_schemas=["public", "pharma", "management"],
    # route_prefix="/api/v1",
    enable_tags=True,
))
# * THE ROUTES MUST BE GENERATED AFTER THE MODELS!
api_forge.generate_routes()
# # * Print the routers
[app.include_router(router) for router in api_forge.routers.values()]
