from typing import Dict, Tuple, Type, List, Callable
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Enum as SQLAlchemyEnum
from pydantic import BaseModel

from crud_forge.db import DatabaseManager, EnumMetadata

class EnumInfo(BaseModel):
    name: str
    values: List[str]

def from_metadata(
    db_manager: DatabaseManager
) -> Dict[str, Dict[str, Tuple[Type[SQLAlchemyEnum], Type[Enum]]]]:
    """
    Generate SQLAlchemy and Python Enums from DatabaseManager enum metadata.

    Args:
        enums: Dictionary of enum metadata from DatabaseManager.

    Returns:
        Dict[str, Dict[str, Tuple[Type[SQLAlchemyEnum], Type[Enum]]]]: A dictionary of generated Enums.
    """
    combined_enums: Dict[str, Dict[str, Tuple[Type[SQLAlchemyEnum], Type[Enum]]]] = {}

    for schema_name, schema_enums in db_manager.enums.items():
        print(f"\n\033[93m[Schema]\033[0m {schema_name}")
        schema_combined_enums: Dict[str, Tuple[Type[SQLAlchemyEnum], Type[Enum]]] = {}

        for enum_name, enum_metadata in schema_enums.items():
            print(f"\n\t\033[96m[Enum]\033[0m \033[1m{schema_name}.\033[4m{enum_name}\033[0m")
            
            sqlalchemy_enum = SQLAlchemyEnum(*enum_metadata.values, name=enum_name)
            print(f"\t    \033[94m[SQLAlchemy]_Enum:\033[0m {enum_name}")

            python_enum = Enum(enum_name, {v: v for v in enum_metadata.values})
            print(f"\t    \033[92m[  Python  ]_Enum:\033[0m {enum_name}")

            for value in enum_metadata.values:
                print(f"\t\t{value}")

            schema_combined_enums[enum_name] = (sqlalchemy_enum, python_enum)

        combined_enums[schema_name] = schema_combined_enums

    return combined_enums

def gen_enum_routes(
    enum_metadata: Dict[str, Dict[str, EnumMetadata]],
    db_dependency: Callable
) -> APIRouter:
    """Generate enum routes for the API."""
    enum_router: APIRouter = APIRouter(prefix="/enums", tags=["Enums"])

    @enum_router.get("/schemas", response_model=List[str])
    def get_enum_schemas(db: Session = Depends(db_dependency)) -> List[str]:
        """Get the list of schemas containing enums."""
        return list(enum_metadata.keys())

    @enum_router.get("/{schema}", response_model=List[str])
    def get_schema_enums(schema: str, db: Session = Depends(db_dependency)) -> List[str]:
        """Get the list of enums in a schema."""
        try:
            return list(enum_metadata[schema].keys())
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Schema '{schema}' not found")

    @enum_router.get("/{schema}/{enum_name}", response_model=List[str])
    def get_enum_info(schema: str, enum_name: str, db: Session = Depends(db_dependency)) -> EnumInfo:
        """Get the information for a specific enum."""
        try:
            return enum_metadata[schema][enum_name].values
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Enum '{enum_name}' not found in schema '{schema}'")

    return enum_router
