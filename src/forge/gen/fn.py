from typing import Any, Callable, Dict, List, Optional, Type, Union, TypeVar
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.engine import Connection
from pydantic import BaseModel, create_model, Field, ConfigDict
from sqlalchemy import text, MetaData
from enum import Enum
import logging
from dataclasses import dataclass
from forge.utils.sql_types import get_eq_type

logger = logging.getLogger(__name__)

# Type variables for better type hints
T = TypeVar('T', bound=BaseModel)

@dataclass
class FunctionParameter:
    """Represents a database function parameter with rich metadata"""
    name: str
    type_name: str
    python_type: Type
    description: Optional[str] = None
    is_optional: bool = False
    default_value: Optional[Any] = None

    @property
    def pydantic_field(self) -> tuple:
        """Generate a Pydantic field tuple for this parameter"""
        field_type = Optional[self.python_type] if self.is_optional else self.python_type
        return (field_type, Field(description=self.description, default=self.default_value))

class DatabaseFunction(BaseModel):
    """Rich representation of a database function with metadata"""
    name: str
    schema: str
    returns: str
    parameters: List[FunctionParameter] = []
    description: str = ""
    is_procedure: bool = False
    is_mutation: bool = False
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    @property
    def full_name(self) -> str:
        """Get the fully qualified function name"""
        return f"{self.schema}.{self.name}"
    
    @property
    def route_path(self) -> str:
        """Get the API route path for this function"""
        return f"/{self.schema}/{self.name}"

class FunctionDocParser:
    """Parses PostgreSQL function documentation"""
    
    @staticmethod
    def parse(doc_string: str) -> Dict[str, Any]:
        """Parse function documentation into description and parameter docs"""
        if not doc_string:
            return {"description": "", "params": {}}

        parts = doc_string.split('@param')
        return {
            "description": parts[0].strip(),
            "params": {
                param.split('-', 1)[0].strip(): param.split('-', 1)[1].strip()
                for param in parts[1:]
                if '-' in param
            }
        }

class DatabaseFunctionScanner:
    """Scans database for functions and creates their representations"""

    def __init__(self, metadata: MetaData):
        self.metadata = metadata
        self._mutation_keywords = {'create', 'update', 'delete', 'insert', 'modify', 'upsert'}

    def _is_mutation(self, func_name: str, params: List[FunctionParameter]) -> bool:
        """Determine if a function modifies data"""
        return any(keyword in func_name.lower() for keyword in self._mutation_keywords) or \
               any(param.type_name.lower() == 'uuid' and 'id' in param.name.lower() 
                   for param in params)

    def _parse_parameters(self, args_str: str, docs: Dict[str, str]) -> List[FunctionParameter]:
        """Parse function parameters from argument string"""
        if not args_str:
            return []

        parameters = []
        for arg in (arg.strip() for arg in args_str.split(',') if arg.strip()):
            parts = arg.split(' ')
            if len(parts) >= 2:
                name = parts[0].strip('_')
                type_name = ' '.join(parts[1:]).lower()
                
                parameters.append(FunctionParameter(
                    name=name,
                    type_name=type_name,
                    python_type=get_eq_type(type_name),
                    description=docs.get("params", {}).get(name),
                    is_optional='DEFAULT' in parts
                ))

        return parameters

    def scan_schema(self, conn: Connection, schema: str) -> List[DatabaseFunction]:
        """Scan a database schema for functions"""
        query = text("""
            SELECT 
                p.proname as name,
                n.nspname as schema,
                pg_get_function_identity_arguments(p.oid) as args,
                CASE 
                    WHEN p.prokind = 'p' THEN 'void'
                    ELSE pg_get_function_result(p.oid)
                END as returns,
                COALESCE(obj_description(p.oid, 'pg_proc'), '') as description,
                p.prokind = 'p' as is_procedure
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            WHERE n.nspname = :schema
            AND p.proname NOT LIKE 'pg_%'
            ORDER BY p.proname;
        """)

        functions = []
        result = conn.execute(query, {"schema": schema})
        
        for row in result:
            docs = FunctionDocParser.parse(row.description)
            parameters = self._parse_parameters(row.args, docs)
            
            function = DatabaseFunction(
                name=row.name,
                schema=row.schema,
                returns=row.returns,
                parameters=parameters,
                description=docs["description"],
                is_procedure=row.is_procedure,
                is_mutation=self._is_mutation(row.name, parameters)
            )
            
            functions.append(function)

        return functions

class FunctionRouteGenerator:
    """Generates FastAPI routes for database functions"""

    def __init__(self, db_dependency: Callable[[], Session]):
        self.db_dependency = db_dependency
        self.scanner = None

    def _create_params_model(self, function: DatabaseFunction) -> Optional[Type[BaseModel]]:
        """Create a Pydantic model for function parameters"""
        if not function.parameters:
            return None

        return create_model(
            f"{function.name.title()}Params",
            **{p.name: p.pydantic_field for p in function.parameters}
        )

    def _create_response_model(self, function: DatabaseFunction) -> Type[BaseModel]:
        """Create a Pydantic model for function response"""
        return_type = get_eq_type(function.returns or 'text')
        return create_model(
            f"{function.name.title()}Response",
            result=(return_type, Field(...))
        )

    def _create_route_handler(self, function: DatabaseFunction, params_model: Optional[Type[BaseModel]]):
        """Create a route handler for a database function"""
        
        def handler(db: Session = Depends(self.db_dependency), **kwargs):
            try:
                # Filter out None values and prepare parameters
                param_dict = {k: v for k, v in kwargs.items() if v is not None}
                
                # Build parameter list for the query
                if param_dict:
                    param_list = [f"{k} => :{k}" for k in param_dict.keys()]
                    query = text(f"SELECT {function.full_name}({', '.join(param_list)})")
                else:
                    query = text(f"SELECT {function.full_name}()")
                
                logger.info(f"Executing query: {query}")
                logger.info(f"With parameters: {param_dict}")
                
                with db.begin():
                    result = db.execute(query, param_dict)
                    return {"result": result.scalar()}

            except Exception as e:
                logger.error(f"Error executing {function.full_name}: {str(e)}")
                db.rollback()
                raise HTTPException(
                    status_code=500,
                    detail=f"Error executing function: {str(e)}"
                )

        # Add fastapi route parameters based on the function's parameters
        if function.parameters:
            for param in function.parameters:
                kwargs = {}
                if param.description:
                    kwargs['description'] = param.description
                if param.is_optional:
                    kwargs['default'] = None
                
                handler.__annotations__[param.name] = param.python_type
        
        return handler

    def generate_routes(
        self, 
        router: APIRouter, 
        schemas: List[str] = ['public'],
        metadata: MetaData = None
    ) -> None:
        """Generate routes for all functions in specified schemas"""
        self.scanner = DatabaseFunctionScanner(metadata)
        
        for schema in schemas:
            try:
                db = next(self.db_dependency())
                functions = self.scanner.scan_schema(db.connection(), schema)
                
                for function in functions:
                    params_model = self._create_params_model(function)
                    response_model = self._create_response_model(function)
                    handler = self._create_route_handler(function, params_model)
                    
                    route_params = {
                        "path": function.route_path,
                        "response_model": response_model,
                        "description": function.description,
                    }
                    
                    # Register route based on function type
                    if function.is_mutation or function.is_procedure:
                        router.post(**route_params)(handler)
                    else:
                        router.get(**route_params)(handler)
                    
                    logger.info(
                        f"Registered route: {'POST' if function.is_mutation else 'GET'} "
                        f"{function.route_path}"
                    )

            except Exception as e:
                logger.error(f"Error generating routes for schema {schema}: {str(e)}")
                raise

def register_db_functions(
    router: APIRouter,
    db_dependency: Callable[[], Session],
    schemas: List[str] = ['public'],
    metadata: Optional[MetaData] = None
) -> None:
    """
    Register database functions as API routes.
    
    Args:
        router: FastAPI router to add routes to
        db_dependency: Database session dependency
        schemas: List of database schemas to scan
        metadata: SQLAlchemy metadata (optional)
    """
    generator = FunctionRouteGenerator(db_dependency)
    generator.generate_routes(router, schemas, metadata)
