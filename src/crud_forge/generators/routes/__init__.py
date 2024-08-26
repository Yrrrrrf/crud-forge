from crud_forge.db import SchemaMetadata, ColumnMetadata, TableMetadata
from fastapi import APIRouter, Depends, HTTPException, FastAPI
from typing import List, Dict, Callable
from sqlalchemy.orm import Session

from . import crud as crud  # * INITIALIZED (called as: 'routes.crud.some_fn()')


# needs the app instance to read some of its attributes
def gen_default_routes(app: FastAPI) -> None:
    default_router: APIRouter = APIRouter(tags=["Default"])

    @default_router.get("/")
    async def root() -> Dict[str, str]:
        """Root endpoint that provides basic information about the API."""
        return {
            "message": f"Welcome to the {app.title}",
            "version": app.version,
            "description": app.description
        }

    @default_router.get("/health")
    async def health_check() -> Dict[str, str]: return {"status": "healthy", "version": app.version}

    @default_router.get("/version")
    async def version() -> Dict[str, str]: return {"version": app.version}

    app.include_router(default_router)


def gen_metadata_routes(
    db_metadata: Dict[str, SchemaMetadata],
    db_dependency: Callable
) -> APIRouter:  # * Return the APIRouter instance with the metadata routes
    """Generate metadata for the database."""
    metadata: APIRouter = APIRouter(prefix="/dt", tags=["Metadata"])

    @metadata.get("/schemas", response_model=List[str])
    def get_schemas(db: Session = Depends(db_dependency)) -> List[str]:
        """Get the list of schemas in the database."""
        return list(db_metadata.keys())

    # ^ I think that the response model should be a list of TableMetadata
    # ^ But I also think that the TableMetadata contains so much information that it is not necessary to return it all
    # ^ So, I think that the response model should be a list of strings
    # todo: Check what is the correct response model for this endpoint...
    @metadata.get("/{schema}/tables", response_model=List[TableMetadata])
    def get_tables(schema: str, db: Session = Depends(db_dependency)) -> List[TableMetadata]:
        """Get the list of tables in a schema."""
        try:
            return list(db_metadata[schema].tables.values())  # if response model is List[TableMetadata]
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Schema '{schema}' not found")

    @metadata.get("/{schema}/{table}/columns", response_model=List[ColumnMetadata])
    def get_columns(schema: str, table: str, db: Session = Depends(db_dependency)) -> List[ColumnMetadata]:
        """Get the list of columns in a table."""
        try:
            return db_metadata[schema].tables[table].columns
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Table '{table}' not found in schema '{schema}'")

    return metadata
