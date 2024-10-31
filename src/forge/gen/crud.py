from typing import Callable, List, Dict, Any, Optional, Type, Union
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import Table
from pydantic import BaseModel, create_model
from enum import Enum
from sqlalchemy import Enum as SQLAlchemyEnum
from enum import Enum as PyEnum

def _get_route_params(
    table: Table, 
    response_model: Type[Any], 
    tags: Optional[List[Union[str, Enum]]] = None
) -> Dict[str, Any]:
    """Generate route parameters for FastAPI router decorators."""
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
        sqlalchemy_model: Type[Any],  # ^ Added sqlalchemy_model parameter
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add a CREATE route for a specific table."""
    
    @router.post(**_get_route_params(table, pydantic_model, tags))
    def create_resource(
            resource: pydantic_model,
            db: Session = Depends(db_dependency)
    ) -> pydantic_model:
        data = resource.model_dump(exclude_unset=True)
        for column in table.columns:
            if column.type.python_type == uuid.UUID:
                data.pop(column.name, None)
        try:
            db_resource = sqlalchemy_model(**data)  # ^ Use sqlalchemy_model instead of DynamicModel
            db.add(db_resource)
            db.commit()
            db.refresh(db_resource)
            result_dict = {column.name: getattr(db_resource, column.name) for column in table.columns}
            return pydantic_model(**result_dict)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Creation failed: {str(e)}")

def get_route(
        table: Table,
        pydantic_model: Type[BaseModel],
        sqlalchemy_model: Type[Any],
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add a GET route for a specific table."""
    
    # Create a proper Pydantic model for query parameters
    query_fields = {
        field_name: (Optional[field.annotation], None) 
        for field_name, field in pydantic_model.model_fields.items()
    }
    
    QueryParams = create_model(
        f"{pydantic_model.__name__}QueryParams",
        **query_fields,
        __base__=BaseModel
    )

    @router.get(
        **_get_route_params(table, List[pydantic_model], tags),
        summary=f"Get {table.name} resources",
        description=f"Retrieve {table.name} records with optional filtering"
    )
    def read_resources(
            db: Session = Depends(db_dependency),
            filters: QueryParams = Depends()
    ) -> List[pydantic_model]:
        query_obj = db.query(sqlalchemy_model)
        filters_dict = filters.model_dump(exclude_unset=True)

        for column_name, value in filters_dict.items():
            if value is not None:
                column = getattr(sqlalchemy_model, column_name)
                if isinstance(column.type, SQLAlchemyEnum):
                    # Handle enum values
                    if isinstance(value, str):
                        query_obj = query_obj.filter(column == value)
                    elif isinstance(value, PyEnum):
                        query_obj = query_obj.filter(column == value.value)
                else:
                    query_obj = query_obj.filter(column == value)

        resources = query_obj.all()
        return [pydantic_model.model_validate(resource.__dict__) for resource in resources]


def update_route(
        table: Table,
        pydantic_model: Type[BaseModel],
        sqlalchemy_model: Type[Any],  # ^ Added sqlalchemy_model parameter
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add an UPDATE route for a specific table."""
    
    @router.put(**_get_route_params(table, Dict[str, Any], tags))
    def update_resource(
            resource: pydantic_model,
            db: Session = Depends(db_dependency),
            query_params: pydantic_model = Depends()
    ) -> Dict[str, Any]:
        update_data = resource.model_dump(exclude_unset=True)
        filters_dict = query_params.model_dump(exclude_unset=True)

        if not filters_dict:
            raise HTTPException(status_code=400, detail="No filters provided.")

        try:
            query = db.query(sqlalchemy_model)

            for attr, value in filters_dict.items():
                if value is not None:
                    query = query.filter(getattr(sqlalchemy_model, attr) == value)

            old_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            if not old_data:
                raise HTTPException(status_code=404, detail="No matching resources found.")

            updated_count = query.update(update_data)
            db.commit()

            updated_data = [pydantic_model.model_validate(data.__dict__) for data in query.all()]

            return {
                "updated_count": updated_count,
                "old_data": [d.model_dump() for d in old_data],
                "updated_data": [d.model_dump() for d in updated_data]
            }

        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Update failed: {str(e)}")

# todo: Fix the error, when deleting some object, it returns a Null object
# todo: instead of the object that was deleted
# todo:     (e.g. {"message": "1 resource(s) deleted successfully", "deleted_resources": [null]})
def delete_route(
        table: Table,
        pydantic_model: Type[BaseModel],
        sqlalchemy_model: Type[Any],  # ^ Added sqlalchemy_model parameter
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Add a DELETE route for a specific table."""

    @router.delete(**_get_route_params(table, Dict[str, Any], tags))
    def delete_resource(
            db: Session = Depends(db_dependency),
            query_params: pydantic_model = Depends()
    ) -> Dict[str, Any]:
        filters_dict = query_params.model_dump(exclude_unset=True)
        
        if not filters_dict:
            raise HTTPException(status_code=400, detail="No filters provided")

        query = db.query(sqlalchemy_model)
        for attr, value in filters_dict.items():
            if value is not None:
                query = query.filter(getattr(sqlalchemy_model, attr) == value)
        
        try:
            deleted = query.all()
            if not deleted:
                return {"message": "No resources found matching the criteria"}
            
            deleted_count = query.delete(synchronize_session=False)
            db.commit()
            
            return {"message": f"{deleted_count} resource(s) deleted successfully", "deleted_resources": [pydantic_model.model_validate(d.__dict__).model_dump() for d in deleted]}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Deletion failed: {str(e)}")

# * All CRUD routes

def gen_crud(
        table: Table,
        pydantic_model: Type[BaseModel],
        sqlalchemy_model: Type[Any],  # ^ Added sqlalchemy_model parameter
        router: APIRouter,
        db_dependency: Callable,
        tags: Optional[List[Union[str, Enum]]] = None
) -> None:
    """Generate CRUD routes for a specific table."""
    [func(table, pydantic_model, sqlalchemy_model, router, db_dependency, tags) for func in [
        create_route, get_route, update_route, delete_route
    ]]

#     def _should_generate_routes(self, table: Table) -> bool:
#         schema = table.schema or 'public'
#         schema_included = not self.include_schemas or schema in self.include_schemas
#         table_not_excluded = table.name not in self.exclude_tables
#         return schema_included and table_not_excluded

#     def _genr_table_crud(self, table: Table, db_dependency: Callable) -> None:
#         pydantic_model = self._get_pydantic_model(table)
#         sqlalchemy_model = self._get_sqlalchemy_model(table)

#         for route_generator in [create_route, get_route, update_route, delete_route]:
#             route_generator(
#                 table=table,
#                 pydantic_model=pydantic_model,
#                 sqlalchemy_model=sqlalchemy_model,
#                 router=self.router,
#                 db_dependency=db_dependency
#             )

#     def genr_crud(self) -> APIRouter:
#         for _, table in self.db_manager.metadata.tables.items():
#             if self._should_generate_routes(table):
#                 self._genr_table_crud(table, self.db_manager.get_db)
#         return self.router
