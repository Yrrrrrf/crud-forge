# CRUD FORGE

[![PyPI version](https://badge.fury.io/py/fastapi-crud-gen.svg)](https://badge.fury.io/py/fastapi-crud-gen)
[![Documentation Status](https://readthedocs.org/projects/fastapi-crud-gen/badge/?version=latest)](https://fastapi-crud-gen.readthedocs.io/en/latest/?badge=latest)

CRUD FORGE is a powerful Python package that simplifies the creation of CRUD (Create, Read, Update, Delete) operations for FastAPI applications. It automatically generates API routes and database models based on your SQLAlchemy models, saving you time and reducing boilerplate code.

## Features

- Automatic generation of CRUD routes for FastAPI
- Support for SQLAlchemy models and Pydantic schemas
- Flexible database connection management
- Easy-to-use API for creating models and routes
- Customizable route generation
- Built-in filtering for GET requests
- Comprehensive error handling
- Type hinting for better IDE support

## Installation

Install FastAPI CRUD Generator using pip:

```bash
pip install crud-forge
```

## Quick Start

Here's a simple example of how to use FastAPI CRUD Generator:

```python
from fastapi import FastAPI
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from crud_forge.generators import generate_crud
from crud_forge.db import DatabaseManager

# Define your SQLAlchemy model
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)

# Define your Pydantic model
class UserSchema(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        orm_mode = True

# Set up FastAPI app and database
app = FastAPI()
db_manager = DatabaseManager(db_url="postgresql://user:password@localhost/dbname")

# Generate CRUD routes
generate_crud(User, UserSchema, app, db_manager.get_db)

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

[//]: # (show the svg of docs/images/pkg.svg)

## Package Structure
![CRUD FORGE](docs/images/pkg.svg)


This example sets up a simple User model and generates CRUD routes for it.

## Usage

### Setting up the Database Connection

Use the `DatabaseManager` class to manage your database connection:

```python
from crud_forge.db import DatabaseManager

db_manager = DatabaseManager(
    user="myuser",
    password="mypassword",
    host="localhost",
    database="mydatabase"
)
```

Or provide a complete database URL:

```python
db_manager = DatabaseManager(db_url="postgresql://user:password@localhost/dbname")
```

### Generating Models

Use the `generators.models` module to generate SQLAlchemy & Pydantic models from your database:

```python
from crud_forge.generators.models import generate_models, generate_views
from crud_forge.db import DatabaseManager

db_manager = DatabaseManager(db_url="postgresql://user:password@localhost/dbname")

store_models = generate_models(db_manager.engine, ['store'])
store_views = generate_views(db_manager.engine, ['store'])
```

### Creating CRUD Routes

Use the `create_crud_routes` function to automatically generate CRUD routes for your models:

```python
from crud_forge.generators.crud import generate_crud

generate_crud(sqlalchemy_model, pydantic_model, router, db_dependency)
```

This will create the following routes:

- `GET /users/columns`: Get all columns of the User model
- `POST /users`: Create a new user
- `GET /users`: Get all users (with optional filtering)
- `PUT /users`: Update users (with filtering)
- `DELETE /users`: Delete users (with filtering)

## Documentation

For more detailed information about the API and advanced usage, please refer to our [documentation](https://fastapi-crud-gen.readthedocs.io).

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for more details.

## License

FastAPI CRUD Generator is released under the MIT License. See the [LICENSE](LICENSE) file for more details.


