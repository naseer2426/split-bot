import logging
from datetime import datetime
from typing import Optional, List 
from dataclasses import dataclass
from psycopg.errors import UniqueViolation
from db import get_connection

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class User:
    """User model representing the split_bot_users table."""
    id: int
    name: str
    email: str
    telegram_username: Optional[str]
    whatsapp_number: Optional[str]
    whatsapp_lid: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    def __str__(self):
        return f"User(id={self.id}, name={self.name}, email={self.email})"
    
    def __repr__(self):
        return self.__str__()


def _row_to_user(row: tuple) -> User:
    """Convert a database row tuple to a User object."""
    return User(
        id=row[0],
        name=row[1],
        email=row[2],
        telegram_username=row[3],
        whatsapp_number=row[4],
        whatsapp_lid=row[5],
        created_at=row[6],
        updated_at=row[7]
    )


def init_users_table():
    """
    Initialize the split_bot_users table if it doesn't exist.
    Creates the table with the following schema:
    - id: SERIAL PRIMARY KEY (auto increment, unique)
    - name: VARCHAR(255) NOT NULL
    - email: VARCHAR(255) NOT NULL
    - telegram_username: VARCHAR(255) NULL
    - whatsapp_number: VARCHAR(50) NULL
    - whatsapp_lid: VARCHAR(255) NULL
    - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    - updated_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Create table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS split_bot_users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    telegram_username VARCHAR(255) NULL,
                    whatsapp_number VARCHAR(50) NULL,
                    whatsapp_lid VARCHAR(255) NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add whatsapp_lid column if it doesn't exist (for existing tables)
            cur.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='split_bot_users' AND column_name='whatsapp_lid'
                    ) THEN
                        ALTER TABLE split_bot_users ADD COLUMN whatsapp_lid VARCHAR(255) NULL;
                    END IF;
                END $$;
            """)
            
            conn.commit()
            logger.info("Table split_bot_users initialized/verified")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing table: {str(e)}")
        raise


# CRUD Functions

def create_user(
    name: str,
    email: str,
    telegram_username: Optional[str] = None,
    whatsapp_number: Optional[str] = None,
    whatsapp_lid: Optional[str] = None
) -> User:
    """
    Create a new user.
    
    Args:
        name: User's name (required)
        email: User's email (required, must be unique)
        telegram_username: User's Telegram username (optional)
        whatsapp_number: User's WhatsApp number (optional)
        whatsapp_lid: User's WhatsApp LID (optional)
    
    Returns:
        User: The created user object
    
    Raises:
        UniqueViolation: If email already exists
        ValueError: If required fields are missing
    """
    if not name or not email:
        raise ValueError("Name and email are required fields")
    
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO split_bot_users (name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                """,
                (
                    name.strip(),
                    email.strip().lower(),
                    telegram_username.strip() if telegram_username else None,
                    whatsapp_number.strip() if whatsapp_number else None,
                    whatsapp_lid.strip() if whatsapp_lid else None,
                    datetime.now(),
                    datetime.now()
                )
            )
            row = cur.fetchone()
            conn.commit()
            user = _row_to_user(row)
            logger.info(f"Created user: {user}")
            return user
    except UniqueViolation as e:
        conn.rollback()
        logger.error(f"Error creating user: {str(e)}")
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error creating user: {str(e)}")
        raise


def get_user_by_id(user_id: int) -> Optional[User]:
    """
    Get a user by their ID.
    
    Args:
        user_id: The user's ID
    
    Returns:
        User: The user object if found, None otherwise
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                FROM split_bot_users
                WHERE id = %s
                """,
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                return _row_to_user(row)
            logger.debug(f"User with id {user_id} not found")
            return None
    except Exception as e:
        logger.error(f"Error getting user by id: {str(e)}")
        raise


def get_user_by_email(email: str) -> Optional[User]:
    """
    Get a user by their email.
    
    Args:
        email: The user's email address
    
    Returns:
        User: The user object if found, None otherwise
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                FROM split_bot_users
                WHERE email = %s
                """,
                (email.strip().lower(),)
            )
            row = cur.fetchone()
            if row:
                return _row_to_user(row)
            logger.debug(f"User with email {email} not found")
            return None
    except Exception as e:
        logger.error(f"Error getting user by email: {str(e)}")
        raise


def get_user_by_telegram_username(telegram_username: str) -> Optional[User]:
    """
    Get a user by their Telegram username.
    
    Args:
        telegram_username: The user's Telegram username
    
    Returns:
        User: The user object if found, None otherwise
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                FROM split_bot_users
                WHERE telegram_username = %s
                """,
                (telegram_username.strip(),)
            )
            row = cur.fetchone()
            if row:
                return _row_to_user(row)
            logger.debug(f"User with telegram_username {telegram_username} not found")
            return None
    except Exception as e:
        logger.error(f"Error getting user by telegram_username: {str(e)}")
        raise


def get_user_by_whatsapp_number(whatsapp_number: str) -> Optional[User]:
    """
    Get a user by their WhatsApp number.
    
    Args:
        whatsapp_number: The user's WhatsApp number
    
    Returns:
        User: The user object if found, None otherwise
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                FROM split_bot_users
                WHERE whatsapp_number = %s
                """,
                (whatsapp_number.strip(),)
            )
            row = cur.fetchone()
            if row:
                return _row_to_user(row)
            logger.debug(f"User with whatsapp_number {whatsapp_number} not found")
            return None
    except Exception as e:
        logger.error(f"Error getting user by whatsapp_number: {str(e)}")
        raise


def get_user_by_whatsapp_lid(whatsapp_lid: str) -> Optional[User]:
    """
    Get a user by their WhatsApp LID.
    
    Args:
        whatsapp_lid: The user's WhatsApp LID
    
    Returns:
        User: The user object if found, None otherwise
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                FROM split_bot_users
                WHERE whatsapp_lid = %s
                """,
                (whatsapp_lid.strip(),)
            )
            row = cur.fetchone()
            if row:
                return _row_to_user(row)
            logger.debug(f"User with whatsapp_lid {whatsapp_lid} not found")
            return None
    except Exception as e:
        logger.error(f"Error getting user by whatsapp_lid: {str(e)}")
        raise


def get_all_users(limit: Optional[int] = None, offset: int = 0) -> List[User]:
    """
    Get all users.
    
    Args:
        limit: Maximum number of users to return (optional)
        offset: Number of users to skip (default: 0)
    
    Returns:
        List[User]: List of user objects
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                FROM split_bot_users
                ORDER BY id
                OFFSET %s
            """
            params = [offset]
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            cur.execute(query, params)
            rows = cur.fetchall()
            return [_row_to_user(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting all users: {str(e)}")
        raise


def update_user(
    user_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    telegram_username: Optional[str] = None,
    whatsapp_number: Optional[str] = None,
    whatsapp_lid: Optional[str] = None
) -> Optional[User]:
    """
    Update a user's information.
    
    Args:
        user_id: The user's ID
        name: New name (optional)
        email: New email (optional, must be unique)
        telegram_username: New Telegram username (optional, use empty string to clear)
        whatsapp_number: New WhatsApp number (optional, use empty string to clear)
        whatsapp_lid: New WhatsApp LID (optional, use empty string to clear)
    
    Returns:
        User: The updated user object if found, None otherwise
    
    Raises:
        UniqueViolation: If email already exists for another user
    """
    conn = get_connection()
    try:
        # First check if user exists
        user = get_user_by_id(user_id)
        if not user:
            logger.debug(f"User with id {user_id} not found")
            return None
        
        # Build update query dynamically
        update_fields = []
        params = []
        
        if name is not None:
            update_fields.append("name = %s")
            params.append(name.strip())
        if email is not None:
            update_fields.append("email = %s")
            params.append(email.strip().lower())
        if telegram_username is not None:
            update_fields.append("telegram_username = %s")
            params.append(telegram_username.strip() if telegram_username else None)
        if whatsapp_number is not None:
            update_fields.append("whatsapp_number = %s")
            params.append(whatsapp_number.strip() if whatsapp_number else None)
        if whatsapp_lid is not None:
            update_fields.append("whatsapp_lid = %s")
            params.append(whatsapp_lid.strip() if whatsapp_lid else None)
        
        if not update_fields:
            logger.warning("No fields to update")
            return user
        
        # Always update the updated_at timestamp
        update_fields.append("updated_at = %s")
        params.append(datetime.now())
        
        # Add user_id for WHERE clause
        params.append(user_id)
        
        with conn.cursor() as cur:
            query = f"""
                UPDATE split_bot_users
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
            """
            cur.execute(query, params)
            row = cur.fetchone()
            conn.commit()
            
            if row:
                updated_user = _row_to_user(row)
                logger.info(f"Updated user: {updated_user}")
                return updated_user
            return None
    except UniqueViolation as e:
        conn.rollback()
        logger.error(f"Error updating user: {str(e)}")
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error updating user: {str(e)}")
        raise


def upsert_user_by_email(
    email: str,
    name: Optional[str] = None,
    telegram_username: Optional[str] = None,
    whatsapp_number: Optional[str] = None,
    whatsapp_lid: Optional[str] = None
) -> User:
    """
    Upsert (update or insert) a user by their email address.
    If a user with the email exists, update their information.
    If no user exists, create a new user.
    
    Args:
        email: The user's email address (required, used as the unique identifier)
        name: User's name (required if creating new user, optional if updating)
        telegram_username: User's Telegram username (optional, use empty string to clear)
        whatsapp_number: User's WhatsApp number (optional, use empty string to clear)
        whatsapp_lid: User's WhatsApp LID (optional, use empty string to clear)
    
    Returns:
        User: The upserted user object
    
    Raises:
        ValueError: If name is not provided when creating a new user
        UniqueViolation: If there's a database integrity error
    """
    email = email.strip().lower()
    conn = get_connection()
    
    try:
        # Try to get existing user
        user = get_user_by_email(email)
        
        if user:
            # User exists - update
            update_fields = {}
            if name is not None:
                update_fields["name"] = name.strip()
            if telegram_username is not None:
                update_fields["telegram_username"] = telegram_username.strip() if telegram_username else None
            if whatsapp_number is not None:
                update_fields["whatsapp_number"] = whatsapp_number.strip() if whatsapp_number else None
            if whatsapp_lid is not None:
                update_fields["whatsapp_lid"] = whatsapp_lid.strip() if whatsapp_lid else None
            
            if not update_fields:
                # No fields to update, just return existing user
                return user
            
            # Build update query
            update_clauses = []
            params = []
            for field, value in update_fields.items():
                update_clauses.append(f"{field} = %s")
                params.append(value)
            
            update_clauses.append("updated_at = %s")
            params.append(datetime.now())
            params.append(user.id)
            
            with conn.cursor() as cur:
                query = f"""
                    UPDATE split_bot_users
                    SET {', '.join(update_clauses)}
                    WHERE id = %s
                    RETURNING id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                """
                cur.execute(query, params)
                row = cur.fetchone()
                conn.commit()
                updated_user = _row_to_user(row)
                logger.info(f"Updated user by email (upsert): {updated_user}")
                return updated_user
        else:
            # User doesn't exist - create new user
            if not name:
                raise ValueError("Name is required when creating a new user")
            
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO split_bot_users (name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                        """,
                        (
                            name.strip(),
                            email,
                            telegram_username.strip() if telegram_username else None,
                            whatsapp_number.strip() if whatsapp_number else None,
                            whatsapp_lid.strip() if whatsapp_lid else None,
                            datetime.now(),
                            datetime.now()
                        )
                    )
                    row = cur.fetchone()
                    conn.commit()
                    user = _row_to_user(row)
                    logger.info(f"Created user by email (upsert): {user}")
                    return user
            except UniqueViolation:
                # Race condition: user was created between our check and create
                # Retry as update
                conn.rollback()
                logger.debug(f"User created by another process, retrying as update: {email}")
                user = get_user_by_email(email)
                
                if not user:
                    raise ValueError(f"Failed to retrieve user after race condition: {email}")
                
                update_fields = {}
                if name is not None:
                    update_fields["name"] = name.strip()
                if telegram_username is not None:
                    update_fields["telegram_username"] = telegram_username.strip() if telegram_username else None
                if whatsapp_number is not None:
                    update_fields["whatsapp_number"] = whatsapp_number.strip() if whatsapp_number else None
                if whatsapp_lid is not None:
                    update_fields["whatsapp_lid"] = whatsapp_lid.strip() if whatsapp_lid else None
                
                if not update_fields:
                    return user
                
                update_clauses = []
                params = []
                for field, value in update_fields.items():
                    update_clauses.append(f"{field} = %s")
                    params.append(value)
                
                update_clauses.append("updated_at = %s")
                params.append(datetime.now())
                params.append(user.id)
                
                with conn.cursor() as cur:
                    query = f"""
                        UPDATE split_bot_users
                        SET {', '.join(update_clauses)}
                        WHERE id = %s
                        RETURNING id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                    """
                    cur.execute(query, params)
                    row = cur.fetchone()
                    conn.commit()
                    updated_user = _row_to_user(row)
                    logger.info(f"Updated user by email (upsert, retry): {updated_user}")
                    return updated_user
            except Exception as e:
                conn.rollback()
                logger.error(f"Unexpected error creating user in upsert: {str(e)}")
                raise
                
    except UniqueViolation as e:
        conn.rollback()
        logger.error(f"Error upserting user by email: {str(e)}")
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error upserting user by email: {str(e)}")
        raise


def delete_user(user_id: int) -> bool:
    """
    Delete a user by their ID.
    
    Args:
        user_id: The user's ID
    
    Returns:
        bool: True if user was deleted, False if user was not found
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM split_bot_users WHERE id = %s",
                (user_id,)
            )
            deleted = cur.rowcount > 0
            conn.commit()
            
            if deleted:
                logger.info(f"Deleted user with id {user_id}")
            else:
                logger.debug(f"User with id {user_id} not found")
            return deleted
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting user: {str(e)}")
        raise


def search_users(
    name: Optional[str] = None,
    email: Optional[str] = None,
    telegram_username: Optional[str] = None,
    whatsapp_number: Optional[str] = None,
    whatsapp_lid: Optional[str] = None
) -> List[User]:
    """
    Search for users by various criteria (exact matching).
    Uses OR logic - matches users that satisfy any of the provided criteria.
    
    Args:
        name: Exact name match (optional)
        email: Exact email match (optional)
        telegram_username: Exact telegram username match (optional)
        whatsapp_number: Exact whatsapp number match (optional)
        whatsapp_lid: Exact whatsapp LID match (optional)
    
    Returns:
        List[User]: List of matching user objects
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT id, name, email, telegram_username, whatsapp_number, whatsapp_lid, created_at, updated_at
                FROM split_bot_users
                WHERE 1=0
            """
            params = []
            
            if name:
                query += " OR name = %s"
                params.append(name.strip())
            if email:
                query += " OR email = %s"
                params.append(email.strip().lower())
            if telegram_username:
                query += " OR telegram_username = %s"
                params.append(telegram_username.strip())
            if whatsapp_number:
                query += " OR whatsapp_number = %s"
                params.append(whatsapp_number.strip())
            if whatsapp_lid:
                query += " OR whatsapp_lid = %s"
                params.append(whatsapp_lid.strip())
            
            cur.execute(query, params)
            rows = cur.fetchall()
            return [_row_to_user(row) for row in rows]
    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        raise
