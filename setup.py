from setuptools import setup, find_packages

setup(
    # Package details
    name="crud-forge",
    version="0.1.3",
    description="A package for generating FastAPI CRUD operations and routes",
    url="https://github.com/Yrrrrrf/crud-forge",
    python_requires=">=3.10",

    # Author details
    author="Yrrrrrf",
    author_email="fernandorezacampos@gmail.com",

    # Package structure
    packages=find_packages(where="src"),  # Find packages in the src directory
    package_dir={"": "src"},            # Root package is in the src directory
    package_data={"": ["docs/images/*.svg"]},  # Include all SVG files in the docs/images directory

    install_requires=[  # Add dependencies (install_requires)
        "fastapi>=0.111.0",
        "sqlalchemy>=2.0.30",
        "pydantic>=2.7.1",
    ],

    extras_require={  # Add development dependencies (extras_require)
        "dev": [  # Dependencies for development
            "pytest>=6.2.5,<7.0.0",  # to run tests
            "black>=21.9b0,<22.0.0",  # code formatting
            "isort>=5.9.3,<6.0.0",  # import sorting
            "mypy>=0.910,<1.0",  # static type checking
        ],
    },

    # Metadata to display on PyPI
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    license="MIT",
    classifiers=[
        # "3 - Alpha", "4 - Beta" or "5 - Production/Stable"
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        # Specify the Python versions you support
        "Programming Language :https://test.pypi.org/simple: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
