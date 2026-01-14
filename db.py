import os
import logging
from typing import Optional
from dotenv import load_dotenv
import psycopg

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

# Database connection string
db_connection_string = os.getenv("DB_CONNECTION_STRING")
if not db_connection_string:
    raise ValueError("DB_CONNECTION_STRING environment variable is required")

# Global connection object
_conn: Optional[psycopg.Connection] = None


def get_connection() -> psycopg.Connection:
    """
    Get or create a database connection.
    
    Returns:
        psycopg.Connection: The database connection object
    """
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg.connect(db_connection_string)
    return _conn


def connect_db():
    """Connect to the database."""
    try:
        get_connection()
        logger.info("Connected to database")
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        raise


def close_db():
    """Close the database connection."""
    global _conn
    try:
        if _conn and not _conn.closed:
            _conn.close()
            _conn = None
            logger.info("Closed database connection")
    except Exception as e:
        logger.error(f"Error closing database connection: {str(e)}")
        raise
