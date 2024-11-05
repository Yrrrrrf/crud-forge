"""Main file for showcasing the database structure using DBForge"""
from fastapi import FastAPI, APIRouter
from sqlalchemy import Enum as SQLAlchemyEnum
import os

# Import our enhanced DBForge and related classes
from forge.api import APIForge
from forge.db import DBForge, DBConfig, PoolConfig
from forge.model import ModelForge
from forge.utils import *
# from forge import init_app


# ? Create the FastAPI app ----------------------------------------------------------------------
# print("\033[H\033[J")  # clear terminal

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

# ? DB Forge ------------------------------------------------------------------------------------
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

# ? Model Forge ---------------------------------------------------------------------------------
model_forge: ModelForge = ModelForge(
    db_manager=db_manager,
    include_schemas=[
        'public', 
        'pharma', 
        'management'
    ],
)
model_forge.log_metadata_stats()
# todo: Improve the log_schema_*() fn's to be more informative & also add some 'verbose' flag
# model_forge.log_schema_tables()
# model_forge.log_schema_views()
# * Add some logging to the model_forge...
# [print(f"{bold('Models:')} {table}") for table in model_forge.model_cache]
# [print(f"{bold('Views:')} {view}") for view in model_forge.view_cache]
# [print(f"{bold('PyEnum:')} {enum}") for enum in model_forge.enum_cache]

# ? API Forge -----------------------------------------------------------------------------------
api_forge = APIForge(model_forge=model_forge)
# * THE ROUTES MUST BE GENERATED AFTER THE MODELS!
api_forge.gen_table_routes()
api_forge.gen_view_routes()
# # # * Print the routers
[app.include_router(router) for router in api_forge.routers.values()]
