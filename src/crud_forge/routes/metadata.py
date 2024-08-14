from fastapi import APIRouter, Depends
from typing import List, Dict
from ..db import DatabaseManager
from ..generators.models import generate_models, generate_views

metadata = APIRouter(prefix="/dt", tags=["Metadata"])

# @metadata.get("/schemas", response_model=List[str])
# def get_schemas(db_manager: DatabaseManager = Depends(get_db_manager)):
#     """Get the list of schemas in the database."""
#     with db_manager.engine.connect() as connection:
#         result = connection.execute("SELECT schema_name FROM information_schema.schemata")
#         return [row[0] for row in result]

# @metadata.get("/models/{schema}", response_model=Dict[str, List[str]])
# def get_models(schema: str, db_manager: DatabaseManager = Depends(get_db_manager)):
#     """Get the list of models and views in a schema."""
#     models = generate_models(db_manager.engine, [schema])
#     views = generate_views(db_manager.engine, [schema])
#     return {
#         "tables": list(models.keys()),
#         "views": list(views.keys())
#     }

# @metadata.get("/columns/{schema}/{model}", response_model=List[str])
# def get_columns(schema: str, model: str, db_manager: DatabaseManager = Depends(get_db_manager)):
#     """Get the list of columns in a model."""
#     models = generate_models(db_manager.engine, [schema])
#     views = generate_views(db_manager.engine, [schema])
    
#     if model in models:
#         return list(models[model][0].__table__.columns.keys())
#     elif model in views:
#         return list(views[model][0].__table__.columns.keys())
#     else:
#         raise ValueError(f"Model {model} not found in schema {schema}")