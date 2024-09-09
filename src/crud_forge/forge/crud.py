import logging
from typing import Callable, List, Dict, Any, Optional, Type, Union
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, declarative_base
from sqlalchemy import Table, and_, select, insert, update, delete
from pydantic import BaseModel, create_model
from enum import Enum

Base = declarative_base()

def _get_route_params(
    table: Table, 
    response_model: Type[Any], 
    tags: Optional[List[Union[str, Enum]]] = None
) -> Dict[str, Any]:
    """
    Generate route parameters for FastAPI router decorators.

    Args:
        table (Table): The SQLAlchemy Table object.
        response_model (Type[Any]): The response model for the route.
        tags (Optional[List[Union[str, Enum]]]): Tags for API documentation.

    Returns:
        Dict[str, Any]: A dictionary of route parameters.
    """
    route_params = {
        "path": f"/{table.name.lower()}",
        "response_model": response_model
    }
    if tags: route_params["tags"] = tags
    return route_params


# * CRUD routes

def create_route(
        table: Table,
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add a CREATE route for a specific table."""
    # Dynamically create a SQLAlchemy model based on the table
    class DynamicModel(Base):
        __table__ = table
    
    @router.post(**_get_route_params(table, pydantic_model, tags))
    def create_resource(
            resource: pydantic_model,
            db: Session = Depends(db_dependency)
    ) -> pydantic_model:
        # Convert Pydantic model to dict, excluding unset values
        data = resource.model_dump(exclude_unset=True)
        for column in table.columns:
            if column.type.python_type == uuid.UUID:
                data.pop(column.name, None)
        try:
            # Create a new instance of the dynamic model
            db_resource = DynamicModel(**data)
            
            # Add the new resource to the session and commit
            db.add(db_resource)
            db.commit()

            # Refresh the instance to ensure we have all server-generated values
            db.refresh(db_resource)

            # Convert the ORM model instance to a dictionary
            result_dict = {column.name: getattr(db_resource, column.name) for column in table.columns}
            
            # Return the result as a Pydantic model instance
            return pydantic_model(**result_dict)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Creation failed: {str(e)}")

def get_route(
        table: Table,
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add a GET route for a specific table."""
    @router.get(**_get_route_params(table, List[pydantic_model], tags))
    def read_resources(
            db: Session = Depends(db_dependency),
            filters: pydantic_model = Depends()
    ) -> List[pydantic_model]:
        query = select(table)
        filters_dict: Dict[str, Any] = filters.model_dump(exclude_unset=True)

        for column_name, value in filters_dict.items():
            if value is not None:
                column = getattr(table.c, column_name, None)
                if column is not None:
                    query = query.where(column == value)

        column_names = [column.name for column in table.columns]

        resources = [dict(zip(column_names, row)) for row in db.execute(query).fetchall()]
        return [pydantic_model(**resource) for resource in resources]

def update_route(
        table: Table,
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add an UPDATE route for a specific table."""
    
    # Dynamically create a SQLAlchemy model based on the table
    class DynamicModel(Base):
        __table__ = table
    
    fields = {col.name: (Optional[col.type.python_type], None) for col in table.columns}
    QueryParams = create_model(f"{table.name}UpdateQueryParams", **fields)

    @router.put(**_get_route_params(table, Dict[str, Any], tags))
    def update_resource(
            resource: pydantic_model,
            db: Session = Depends(db_dependency),
            query_params: QueryParams = Depends()
    ) -> Dict[str, Any]:
        update_data = resource.model_dump(exclude_unset=True)
        filters_dict = query_params.model_dump(exclude_unset=True)

        if not filters_dict:
            raise HTTPException(status_code=400, detail="No filters provided.")

        try:
            query = db.query(DynamicModel)

            for attr, value in filters_dict.items():
                if value is not None:
                    query = query.filter(getattr(DynamicModel, attr) == value)

            # Fetch old data
            old_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            if not old_data:
                raise HTTPException(status_code=404, detail="No matching resources found.")

            # Perform update
            updated_count = query.update(update_data)
            db.commit()

            # Fetch updated data
            # todo: FIX THIS
            # * THE METHOD WORKS AS INTENDED BUT THE UPDATED DATA IS NOT RETURNED
            # * THE UPDATED DATA IS UPDATED IN THE DATABASE BUT NOT RETURNED
            # * SO IT MIGHT BE A PROBLEM WITH THE QUERY...
            updated_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            return {
                "updated_count": updated_count,
                "old_data": [d.model_dump() for d in old_data],
                "updated_data": [d.model_dump() for d in updated_data]
            }

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Update failed: {str(e)}")

def delete_route(
        table: Table,
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add a DELETE route for a specific table."""
    fields = {col.name: (Optional[col.type.python_type], None) for col in table.columns}
    QueryParams: Type[BaseModel] = create_model(f"{table.name}DeleteQueryParams", **fields)

    @router.delete(**_get_route_params(table, Dict[str, Any], tags))
    def delete_resource(
            db: Session = Depends(db_dependency),
            query_params: QueryParams = Depends()
    ) -> Dict[str, Any]:
        stmt = delete(table)
        
        where_conditions = []
        for col, value in query_params.model_dump(exclude_unset=True).items():
            if value is not None:
                where_conditions.append(getattr(table.c, col) == value)
        
        if where_conditions: 
            stmt = stmt.where(and_(*where_conditions))
        else:
            raise HTTPException(status_code=400, detail="No filters provided")

        stmt = stmt.returning(*table.c)
        
        try:
            result = db.execute(stmt)
            db.commit()
            deleted = result.fetchall()
            if not deleted:
                return {"message": "No resources found matching the criteria"}
            return {"message": f"{len(deleted)} resource(s) deleted successfully", "deleted_resources": [dict(row) for row in deleted]}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Deletion failed: {str(e)}")


# * All CRUD routes

def gen_crud(
        table: Table,
        pydantic_model: Type[BaseModel],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Generate CRUD routes for a specific table."""
    [func(table, pydantic_model, router, db_dependency, tags) for func in [
        create_route, get_route, update_route, delete_route
    ]]
