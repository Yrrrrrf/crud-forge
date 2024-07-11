from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Optional


class DatabaseManager:
    """
    Manages database connection and session creation.

    This class provides methods to initialize a database connection,
    create sessions, and manage the database URL. It supports both
    individual connection parameters and a complete database URL.

    Attributes:
        db_url (str): The database URL used for connection.
        engine (Engine): SQLAlchemy engine instance.
        SessionLocal (sessionmaker): SQLAlchemy sessionmaker instance.

    Example:
        # Using individual parameters
        db_manager = DatabaseManager(user="my_user", password="my_password", host="localhost", database="my_db")

        # Using a complete URL
        db_manager = DatabaseManager(db_url="postgresql://my_user:my_password@localhost/my_db")
    """

    def __init__(self,
                 db_url: Optional[str] = None,
                 user: Optional[str] = None,
                 password: Optional[str] = None,
                 host: Optional[str] = None,
                 database: Optional[str] = None,
                 port: Optional[int] = 5432
                 ):
        """
        Initialize the DatabaseManager.

        This method sets up the database connection using either a complete URL
        or individual connection parameters. If a complete URL is provided, it
        takes precedence over individual parameters.

        Args:
            db_url (Optional[str]): The complete database URL.
            user (Optional[str]): Database username.
            password (Optional[str]): Database password.
            host (Optional[str]): Database server host.
            database (Optional[str]): Database name.
            port (Optional[int]): Database server port. Defaults to 5432 for PostgreSQL.

        Raises:
            ValueError: If neither a complete URL nor sufficient individual parameters are provided.
        """
        if db_url:
            self.db_url = db_url
        elif all([user, password, host, database]):
            self.db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        else:
            raise ValueError("Either provide a complete db_url or all of user, password, host, and database.")

        self.engine: Engine = create_engine(self.db_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def get_db(self) -> Session:
        """
        Provide a database session.

        This method should be used as a dependency in FastAPI route functions.
        It yields a SQLAlchemy Session object, which is automatically closed
        after the request is processed.

        Yields:
            Session: A SQLAlchemy database session.

        Example:
            @app.get("/items")
            def read_items(db: Session = Depends(db_manager.get_db)):
                # Use the db session here
                pass
        """
        db: Session = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def test_connection(self) -> bool:
        """
        Test the database connection.

        This method attempts to connect to the database and execute a simple query.
        It can be used to verify that the connection parameters are correct and
        the database is accessible.

        Returns:
            bool: True if the connection is successful, False otherwise.

        Example:
            db_manager = DatabaseManager(db_url="postgresql://user:pass@localhost/db")
            if db_manager.test_connection():
                print("Database connection successful")
            else:
                print("Failed to connect to the database")
        """
        try:
            with self.engine.connect() as connection:
                connection.execute("SELECT 1")  # Execute a simple query
                print("Connection test successful")  # Print a success message
            return True
        except Exception as e:
            print(f"Connection test failed: {str(e)}")
            return False
