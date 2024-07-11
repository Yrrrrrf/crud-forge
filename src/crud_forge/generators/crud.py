from typing import Type, Callable, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from sqlalchemy.ext.declarative import DeclarativeMeta as Base


def create_route(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tag: str
) -> None:
    """
    Add a CREATE route for a specific model.

    This function creates a POST endpoint to add a new resource to the database.

    Args:
        sqlalchemy_model (Type[Base]): SQLAlchemy model for database operations.
        pydantic_model (Type[BaseModel]): Pydantic model for request/response validation.
        router (APIRouter): FastAPI router to attach the new route.
        db_dependency (Callable): Function to get database session.
        tag (str): Tag for API documentation.
    """
    model_name: str = sqlalchemy_model.__tablename__.lower()

    @router.post(f"/{model_name}", tags=[tag], response_model=pydantic_model)
    def create_resource(
            resource: pydantic_model,  # Pydantic model instance from request body
            db: Session = Depends(db_dependency)  # Database session
    ) -> Base:
        """Create a new resource in the database."""
        # Convert Pydantic model to SQLAlchemy model
        db_resource = sqlalchemy_model(**resource.model_dump())
        # Add new resource to the database session
        db.add(db_resource)
        try:
            # Commit the transaction
            db.commit()
            # Refresh the object with new data from the database
            db.refresh(db_resource)
        except Exception as e:
            # Rollback in case of error
            db.rollback()
            # Raise HTTP exception with error details
            raise HTTPException(status_code=400, detail=str(e))
        # Return the created resource
        return db_resource


def get_route(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tag: str
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
        tag (str): Tag for API documentation.
    """
    model_name: str = sqlalchemy_model.__tablename__.lower()

    @router.get(f"/{model_name}", tags=[tag], response_model=List[pydantic_model])
    def get_resources(
            db: Session = Depends(db_dependency),  # Database session
            filters: pydantic_model = Depends()  # Query parameters for filtering
    ):
        """Get resources with optional filtering."""
        # Start with a query for all resources of this model
        query = db.query(sqlalchemy_model)
        # Extract non-null filter values from the request
        filters_dict: Dict[str, Any] = filters.model_dump(exclude_unset=True)

        # Apply filters to the query
        for attr, value in filters_dict.items():
            if value is not None:
                # Add a filter for each non-null attribute
                query = query.filter(getattr(sqlalchemy_model, attr) == value)

        # Execute the query and return all matching resources
        return query.all()


def put_route(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tag: str
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
        tag (str): Tag for API documentation.
    """
    model_name: str = sqlalchemy_model.__tablename__.lower()

    @router.put(f"/{model_name}", tags=[tag], response_model=Dict[str, Any])
    def update_resources(
            resource: pydantic_model,  # Pydantic model instance with update data
            db: Session = Depends(db_dependency),  # Database session
            filters: pydantic_model = Depends()  # Query parameters for filtering
    ) -> Dict[str, Any]:
        """
        Update resources based on filters.

        Args:
            resource (pydantic_model): The data to update.
            db (Session): The database session.
            filters (pydantic_model): Filters to apply for the update.

        Returns:
            Dict[str, Any]: A dictionary containing update information.

        Raises:
            HTTPException: If no filters are provided or no matching resources are found.
        """
        # Start with a query for all resources of this model
        query = db.query(sqlalchemy_model)
        # Extract non-null filter values from the request
        filters_dict: Dict[str, Any] = filters.model_dump(exclude_unset=True)

        # Raise an exception if no filters are provided
        if not filters_dict:
            raise HTTPException(status_code=400, detail="No filters provided.")

        # Apply filters to the query
        for attr, value in filters_dict.items():
            if value is not None:
                query = query.filter(getattr(sqlalchemy_model, attr) == value)

        # Prepare update data, excluding unset values and 'id' if present
        update_data = resource.model_dump(exclude_unset=True)
        update_data.pop('id', None)  # Safely remove 'id' if it exists

        try:
            # Fetch the data before update
            old_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            # Perform the update
            updated_count = query.update(update_data)
            db.commit()

            if updated_count == 0:
                raise HTTPException(status_code=404, detail="No matching resources found.")

            # Fetch the updated data
            updated_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            # Prepare the response
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
        tag: str
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
        tag (str): Tag for API documentation.
    """
    model_name: str = sqlalchemy_model.__tablename__.lower()

    @router.delete(f"/{model_name}", tags=[tag], response_model=Dict[str, Any])
    def delete_resources(
            db: Session = Depends(db_dependency),  # Database session
            filters: pydantic_model = Depends()  # Query parameters for filtering
    ) -> Dict[str, Any]:
        """
        Delete resources based on filters.

        Args:
            db (Session): The database session.
            filters (pydantic_model): Filters to apply for the deletion.

        Returns:
            Dict[str, Any]: A dictionary containing deletion information.

        Raises:
            HTTPException: If no filters are provided or no matching resources are found.
        """
        # Start with a query for all resources of this model
        query = db.query(sqlalchemy_model)
        # Extract non-null filter values from the request
        filters_dict: Dict[str, Any] = filters.model_dump(exclude_unset=True)

        # Raise an exception if no filters are provided
        if not filters_dict:
            raise HTTPException(status_code=400, detail="No filters provided.")

        # Apply filters to the query
        for attr, value in filters_dict.items():
            if value is not None:
                query = query.filter(getattr(sqlalchemy_model, attr) == value)

        try:
            # Fetch the data to be deleted
            to_delete = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            # Perform the deletion
            deleted_count = query.delete()
            db.commit()

            if deleted_count == 0:
                raise HTTPException(status_code=404, detail="No matching resources found.")

            # Prepare the response
            return {
                "deleted_count": deleted_count,
                "deleted_resources": [d.model_dump() for d in to_delete]
            }
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=str(e))


def generate_crud(
        sqlalchemy_model: Type[Base],
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
) -> None:
    """
    Generate CRUD routes for a specific model.

    This function creates CREATE, READ, UPDATE, and DELETE routes for the given model.

    Args:
        sqlalchemy_model (Type[Base]): SQLAlchemy model for database operations.
        pydantic_model (Type[BaseModel]): Pydantic model for request/response validation.
        router (APIRouter): FastAPI router to attach the new routes.
        db_dependency (Callable): Function to get database session.
    """
    # Generate a tag for API documentation
    tag: str = sqlalchemy_model.__name__.replace("_", " ")

    create_route(sqlalchemy_model, pydantic_model, router, db_dependency, tag)
    get_route(sqlalchemy_model, pydantic_model, router, db_dependency, tag)
    put_route(sqlalchemy_model, pydantic_model, router, db_dependency, tag)
    delete_route(sqlalchemy_model, pydantic_model, router, db_dependency, tag)
