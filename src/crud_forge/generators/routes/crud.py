from typing import Type, Callable, List, Dict, Any, Optional, Union
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy.ext.declarative import DeclarativeMeta as Base
from enum import Enum


def _get_route_params(
    sqlalchemy_model: Type[Base], 
    response_model: Type[Any], 
    tags: Optional[List[Union[str, Enum]]] = None
) -> Dict[str, Any]:
    """
    Generate route parameters for FastAPI router decorators.

    Args:
        model_name (str): The name of the model (used for the path).
        response_model (Type[Any]): The response model for the route.
        tags (Optional[List[Union[str, Enum]]]): Tags for API documentation.

    Returns:
        Dict[str, Any]: A dictionary of route parameters.
    """
    route_params = {
        "path": f"/{sqlalchemy_model.__tablename__.lower()}",
        "response_model": response_model
    }
    if tags: route_params["tags"] = tags
    return route_params


def create_route(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """
    Add a CREATE route for a specific model.

    This function creates a POST endpoint to add a new resource to the database.

    Args:
        sqlalchemy_model (Type[Base]): SQLAlchemy model for database operations.
        pydantic_model (Type[BaseModel]): Pydantic model for request/response validation.
        router (APIRouter): FastAPI router to attach the new route.
        db_dependency (Callable): Function to get database session.
        tags (Optional[List[Union[str, Enum]]]): Tags for API documentation.
    """
    @router.post(**_get_route_params(sqlalchemy_model, pydantic_model, tags))
    def create_resource(
            resource: pydantic_model,
            db: Session = Depends(db_dependency)
    ) -> Base:
        """Create a new resource in the database."""
        db_resource = sqlalchemy_model(**resource.model_dump())
        db.add(db_resource)
        try:
            db.commit()
            db.refresh(db_resource)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        return db_resource

def get_route(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """
    Add a GET route for a specific model.

    This function creates a GET endpoint to retrieve resources from the database,
    with optional filtering.

    Args:
        sqlalchemy_model (Type[Base]): SQLAlchemy model for database operations.
        pydantic_model (Type[BaseModel]): Pydantic model for request/response validation.
        router (APIRouter): FastAPI router to attach the new route.
        db_dependency (Callable): Function to get database session.
        tags (Optional[List[Union[str, Enum]]]): Tags for API documentation.
    """
    @router.get(**_get_route_params(sqlalchemy_model, List[pydantic_model], tags))
    def read_resources(
            db: Session = Depends(db_dependency),
            filters: pydantic_model = Depends()
    ):
        """Get resources with optional filtering."""
        query = db.query(sqlalchemy_model)
        filters_dict: Dict[str, Any] = filters.model_dump(exclude_unset=True)

        for attr, value in filters_dict.items():
            if value is not None:
                query = query.filter(getattr(sqlalchemy_model, attr) == value)

        return query.all()

def put_route(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """
    Add a PUT route for updating resources of a specific model.

    This function creates a PUT endpoint to update existing resources in the database
    based on provided filters.

    Args:
        sqlalchemy_model (Type[Base]): SQLAlchemy model for database operations.
        pydantic_model (Type[BaseModel]): Pydantic model for request/response validation.
        router (APIRouter): FastAPI router to attach the new route.
        db_dependency (Callable): Function to get database session.
        tags (Optional[List[Union[str, Enum]]]): Tags for API documentation.
    """
    @router.put(**_get_route_params(sqlalchemy_model, Dict[str, Any], tags))
    def update_resources(
            resource: pydantic_model,
            db: Session = Depends(db_dependency),
            filters: pydantic_model = Depends()
    ) -> Dict[str, Any]:
        """Update resources based on filters."""
        query = db.query(sqlalchemy_model)
        filters_dict: Dict[str, Any] = filters.model_dump(exclude_unset=True)

        if not filters_dict:
            raise HTTPException(status_code=400, detail="No filters provided.")

        for attr, value in filters_dict.items():
            if value is not None:
                query = query.filter(getattr(sqlalchemy_model, attr) == value)

        update_data = resource.model_dump(exclude_unset=True)
        update_data.pop('id', None)

        try:
            old_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]
            updated_count = query.update(update_data)
            db.commit()

            if updated_count == 0:
                raise HTTPException(status_code=404, detail="No matching resources found.")

            updated_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            return {
                "updated_count": updated_count,
                "old_data": [d.model_dump() for d in old_data],
                "updated_data": [d.model_dump() for d in updated_data]
            }
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

def delete_route(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """
    Add a DELETE route for removing resources of a specific model.

    This function creates a DELETE endpoint to remove existing resources from the database
    based on provided filters.

    Args:
        sqlalchemy_model (Type[Base]): SQLAlchemy model for database operations.
        pydantic_model (Type[BaseModel]): Pydantic model for request/response validation.
        router (APIRouter): FastAPI router to attach the new route.
        db_dependency (Callable): Function to get database session.
        tags (Optional[List[Union[str, Enum]]]): Tags for API documentation.
    """
    @router.delete(**_get_route_params(sqlalchemy_model, Dict[str, Any], tags))
    def delete_resources(
            db: Session = Depends(db_dependency),
            filters: pydantic_model = Depends()
    ) -> Dict[str, Any]:
        """Delete resources based on filters."""
        query = db.query(sqlalchemy_model)
        filters_dict: Dict[str, Any] = filters.model_dump(exclude_unset=True)

        if not filters_dict:
            raise HTTPException(status_code=400, detail="No filters provided.")

        for attr, value in filters_dict.items():
            if value is not None:
                query = query.filter(getattr(sqlalchemy_model, attr) == value)

        try:
            to_delete = [pydantic_model.model_validate(data.__dict__) for data in query.all()]
            deleted_count = query.delete()
            db.commit()

            if deleted_count == 0:
                raise HTTPException(status_code=404, detail="No matching resources found.")

            return {
                "deleted_count": deleted_count,
                "deleted_resources": [d.model_dump() for d in to_delete]
            }
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

def gen_crud(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """
    Generate CRUD routes for a specific model.

    This function creates CREATE, READ, UPDATE, and DELETE routes for the given model.

    Args:
        sqlalchemy_model (Type[Base]): SQLAlchemy model for database operations.
        pydantic_model (Type[BaseModel]): Pydantic model for request/response validation.
        router (APIRouter): FastAPI router to attach the new routes.
        db_dependency (Callable): Function to get database session.
        tags (Optional[List[Union[str, Enum]]]): Tags for API documentation.
    """
    create_route(sqlalchemy_model, pydantic_model, router, db_dependency, tags)
    get_route(sqlalchemy_model, pydantic_model, router, db_dependency, tags)
    put_route(sqlalchemy_model, pydantic_model, router, db_dependency, tags)
    delete_route(sqlalchemy_model, pydantic_model, router, db_dependency, tags)
