from typing import Dict, List, Optional, Tuple, Type, Any, Callable
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, create_model
from sqlalchemy import text
from forge.utils.sql_types import get_eq_type, ArrayType, JSONBType
from forge.utils import *
from sqlalchemy.orm import Session

class FunctionVolatility(str, Enum):
    IMMUTABLE = "IMMUTABLE"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"

class SecurityType(str, Enum):
    DEFINER = "SECURITY DEFINER"
    INVOKER = "SECURITY INVOKER"

class FunctionType(str, Enum):
    SCALAR = "scalar"
    TABLE = "table"
    SET_RETURNING = "set"
    AGGREGATE = "aggregate"
    WINDOW = "window"

class FunctionParameter(BaseModel):
    name: str
    type: str
    has_default: bool = False
    default_value: Optional[Any] = None
    mode: str = "IN"  # IN, OUT, INOUT, VARIADIC

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )

class FunctionMetadata(BaseModel):
    schema: str
    name: str
    return_type: Optional[str] = None
    parameters: List[FunctionParameter] = Field(default_factory=list)
    type: FunctionType
    volatility: FunctionVolatility
    security_type: SecurityType
    is_strict: bool
    description: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )



class FnForge(BaseModel):
    """Handles PostgreSQL function discovery and route generation."""
    db_dependency: Callable
    include_schemas: List[str]
    exclude_functions: List[str] = Field(default_factory=list)
    
    # Caches for models and metadata
    function_cache: Dict[str, FunctionMetadata] = Field(default_factory=dict)
    model_cache: Dict[str, Tuple[Type[BaseModel], Type[BaseModel]]] = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )

    def generate_function_models(self) -> None:
        """Generate input and output models for functions."""
        for func_id, metadata in self.function_cache.items():
            # Generate input model
            input_fields = {}
            for param in metadata.parameters:
                field_type = get_eq_type(param.type)  # Using your existing function
                input_fields[param.name] = (
                    field_type if param.has_default else field_type,
                    Field(default=param.default_value if param.has_default else ...)
                )
            
            # Create input model
            input_model = create_model(
                f"{metadata.name}_Input",
                __base__=BaseModel,
                **input_fields
            )
            
            # Generate output model
            if metadata.type in (FunctionType.TABLE, FunctionType.SET_RETURNING):
                output_fields = self._parse_table_return(metadata.return_type)
            else:
                output_type = get_eq_type(metadata.return_type)  # Using your existing function
                output_fields = {"result": (output_type, ...)}
                
            output_model = create_model(
                f"{metadata.name}_Output",
                __base__=BaseModel,
                **output_fields
            )
            
            # Cache models
            self.model_cache[func_id] = (input_model, output_model)

# I'll help you improve the FunctionForge (FnForge) class by converting it to a Pydantic model and fixing the model cache issue. Here's the improved version:
# pythonCopyfrom typing import Dict, List, Optional, Type, Any, Callable, Tuple
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import text
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

class FunctionVolatility(str, Enum):
    IMMUTABLE = "IMMUTABLE"
    STABLE = "STABLE"
    VOLATILE = "VOLATILE"

class SecurityType(str, Enum):
    DEFINER = "SECURITY DEFINER"
    INVOKER = "SECURITY INVOKER"

class FunctionType(str, Enum):
    SCALAR = "scalar"
    TABLE = "table"
    SET_RETURNING = "set"
    AGGREGATE = "aggregate"
    WINDOW = "window"

class FunctionParameter(BaseModel):
    name: str
    type: str
    has_default: bool = False
    default_value: Optional[Any] = None
    mode: str = "IN"  # IN, OUT, INOUT, VARIADIC

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )

class FunctionMetadata(BaseModel):
    schema: str
    name: str
    return_type: Optional[str] = None
    parameters: List[FunctionParameter] = Field(default_factory=list)
    type: FunctionType
    volatility: FunctionVolatility
    security_type: SecurityType
    is_strict: bool
    description: Optional[str] = None

    model_config = ConfigDict(
        from_attributes=True,
        arbitrary_types_allowed=True
    )

class FnForge(BaseModel):
    """Handles PostgreSQL function discovery and route generation."""
    db_dependency: Callable
    include_schemas: List[str]
    exclude_functions: List[str] = Field(default_factory=list)
    
    # Caches for models and metadata
    function_cache: Dict[str, FunctionMetadata] = Field(default_factory=dict)
    model_cache: Dict[str, Tuple[Type[BaseModel], Type[BaseModel]]] = Field(default_factory=dict)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra='allow'
    )

    def discover_functions(self) -> None:
        """Query system catalogs to discover available functions."""
        query = """
            SELECT 
                n.nspname as schema,
                p.proname as name,
                pg_get_function_identity_arguments(p.oid) as arguments,
                COALESCE(pg_get_function_result(p.oid), 'void') as return_type,
                p.provolatile as volatility,
                p.prosecdef as security_definer,
                p.proisstrict as is_strict,
                d.description,
                p.proretset as returns_set,
                p.prokind as kind,
                p.prosrc as source,  -- Get function source
                p.pronamespace as namespace_oid,  -- Get namespace OID
                p.proowner as owner_oid  -- Get owner OID
            FROM pg_proc p
            JOIN pg_namespace n ON p.pronamespace = n.oid
            LEFT JOIN pg_description d ON p.oid = d.objoid
            WHERE n.nspname = ANY(:schemas)
            -- Exclude PostgreSQL internal functions
            AND p.proname NOT LIKE 'pg_%'  -- Exclude postgres prefixed
            AND p.proname NOT LIKE '_%'    -- Exclude underscore prefixed
            -- Exclude extension-provided functions
            AND NOT EXISTS (
                SELECT 1 
                FROM pg_depend d 
                WHERE d.objid = p.oid 
                AND d.deptype = 'e'  -- 'e' means extension
            )
            -- Exclude functions from specific extensions
            AND NOT EXISTS (
                SELECT 1
                FROM pg_extension ext
                JOIN pg_depend d ON d.refobjid = ext.oid
                WHERE d.objid = p.oid
                AND ext.extname IN (
                    'uuid-ossp',    -- UUID functions
                    'pgcrypto',     -- Cryptographic functions
                    'pg_trgm',      -- Trigram functions
                    'plpgsql'       -- PL/pgSQL handler
                )
            )
            ORDER BY n.nspname, p.proname;
        """
        
        # Common built-in function patterns to exclude
        default_function_patterns = [
            r'^uuid_',          # UUID related functions
            r'^gen_',           # Generic generation functions
            r'^crypt',          # Cryptographic functions
            r'^decrypt',        # Cryptographic functions
            r'^encrypt',        # Cryptographic functions
            r'^armor',          # PGP armor functions
            r'^dearmor',        # PGP armor functions
            r'^gin_',           # GIN index functions
            r'^gtrgm_',        # Trigram functions
            r'^similarity',     # Similarity functions
            r'^word_similarity', # Word similarity functions
            r'^strict_word_similarity', # Strict word similarity functions
            r'^digest',         # Hash functions
            r'^hmac',          # HMAC functions
            r'_trgm$',         # Trigram suffix
        ]
        
        with next(self.db_dependency()) as db:
            result = db.execute(
                text(query), 
                {"schemas": self.include_schemas}
            )
            
            for row in result:
                if row.name in self.exclude_functions:
                    continue
                    
                # Skip functions matching default patterns
                if any(re.match(pattern, row.name) for pattern in default_function_patterns):
                    continue

                # Skip system or extension provided functions
                if (
                    not row.description  # Most custom functions have descriptions
                    and not row.source   # And meaningful source code
                    and row.schema == 'public'  # And are not in public schema
                ):
                    continue
                    
                fn_type = self._determine_function_type(row)
                parameters = self._parse_parameters(row.arguments)
                
                metadata = FunctionMetadata(
                    schema=row.schema,
                    name=row.name,
                    return_type=row.return_type if row.return_type else 'void',
                    parameters=parameters,
                    type=fn_type,
                    volatility=self._get_volatility(row.volatility),
                    security_type=SecurityType.DEFINER if row.security_definer else SecurityType.INVOKER,
                    is_strict=row.is_strict,
                    description=row.description
                )
                
                self.function_cache[f"{row.schema}.{row.name}"] = metadata

    def generate_function_models(self) -> None:
        """Generate input and output models for functions."""
        for func_id, metadata in self.function_cache.items():
            # Generate input model
            input_fields = {}
            for param in metadata.parameters:
                field_type = get_eq_type(param.type)
                
                # Handle ArrayType case
                if isinstance(field_type, ArrayType):
                    field_type = List[field_type.item_type]
                
                input_fields[param.name] = (
                    field_type if param.has_default else field_type,
                    Field(default=param.default_value if param.has_default else ...)
                )
            
            # Create input model
            input_model = create_model(
                f"{metadata.name}_Input",
                __base__=BaseModel,
                **input_fields
            )
            
            # Generate output model
            if metadata.type in (FunctionType.TABLE, FunctionType.SET_RETURNING):
                output_fields = self._parse_table_return(metadata.return_type)
            else:
                output_type = get_eq_type(metadata.return_type)
                # Handle ArrayType in output
                if isinstance(output_type, ArrayType):
                    output_type = List[output_type.item_type]
                output_fields = {"result": (output_type, ...)}
                
            output_model = create_model(
                f"{metadata.name}_Output",
                __base__=BaseModel,
                **output_fields
            )
            
            # Cache models
            self.model_cache[func_id] = (input_model, output_model)

    def _parse_table_return(self, return_type: str) -> Dict[str, Tuple[Type, Any]]:
        """Parse TABLE and SETOF return types into field definitions."""
        fields = {}
        
        if "TABLE" in return_type:
            # Strip 'TABLE' and parentheses
            columns_str = return_type.replace("TABLE", "").strip("()").strip()
            columns = [col.strip() for col in columns_str.split(",")]
            
            for column in columns:
                name, type_str = column.split(" ", 1)
                field_type = get_eq_type(type_str)
                # Handle ArrayType in table columns
                if isinstance(field_type, ArrayType):
                    field_type = List[field_type.item_type]
                fields[name] = (field_type, ...)
                
        return fields

    def _determine_function_type(self, row: Any) -> FunctionType:
        if row.returns_set:
            return FunctionType.SET_RETURNING
        if "TABLE" in (row.return_type or ""):
            return FunctionType.TABLE
        if row.kind == 'a':
            return FunctionType.AGGREGATE
        if row.kind == 'w':
            return FunctionType.WINDOW
        return FunctionType.SCALAR

    def _get_volatility(self, volatility_char: str) -> FunctionVolatility:
        return {
            'i': FunctionVolatility.IMMUTABLE,
            's': FunctionVolatility.STABLE,
            'v': FunctionVolatility.VOLATILE
        }.get(volatility_char, FunctionVolatility.VOLATILE)

    def _parse_parameters(self, args_str: str) -> List[FunctionParameter]:
        if not args_str:
            return []
            
        parameters = []
        for arg in args_str.split(", "):
            parts = arg.split(" ")
            if len(parts) >= 2:
                param_name = parts[0]
                param_type = " ".join(parts[1:])
                parameters.append(FunctionParameter(
                    name=param_name,
                    type=param_type
                ))
                
        return parameters

    def log_metadata_stats(self) -> None:
        """Print statistics about discovered functions."""
        print(header("FunctionForge Statistics"))
        
        function_counts = {}
        for metadata in self.function_cache.values():
            if metadata.schema not in function_counts:
                function_counts[metadata.schema] = {
                    FunctionType.SCALAR: 0,
                    FunctionType.TABLE: 0,
                    FunctionType.SET_RETURNING: 0,
                    FunctionType.AGGREGATE: 0,
                    FunctionType.WINDOW: 0
                }
            function_counts[metadata.schema][metadata.type] += 1

        print(f"\n{cyan(bullet('Schemas'))}: {bright(len(function_counts))}")
        
        for schema, counts in function_counts.items():
            print(f"\t{magenta(arrow(schema))}")
            for fn_type, count in counts.items():
                if count > 0:
                    print(f"\t\t{dim(fn_type.value + ':'):<20} {green(f'{count:>4}')}")

        total_functions = sum(
            sum(counts.values()) 
            for counts in function_counts.values()
        )
        print(f"\n{bright('Total Functions:')} {total_functions}\n")