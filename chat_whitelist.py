import logging
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass
from psycopg.errors import UniqueViolation
from db import get_connection

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class WhitelistedChat:
    """Model representing the split_bot_chat_whitelist table."""
    id: int
    group_id: str
    platform_type: str
    created_at: datetime
    updated_at: datetime
    
    def __str__(self):
        return f"WhitelistedChat(id={self.id}, group_id={self.group_id}, platform_type={self.platform_type})"
    
    def __repr__(self):
        return self.__str__()


def _row_to_whitelisted_chat(row: tuple) -> WhitelistedChat:
    """Convert a database row tuple to a WhitelistedChat object."""
    return WhitelistedChat(
        id=row[0],
        group_id=row[1],
        platform_type=row[2],
        created_at=row[3],
        updated_at=row[4]
    )


def init_chat_whitelist_table():
    """
    Initialize the split_bot_chat_whitelist table if it doesn't exist.
    Creates the table with the following schema:
    - id: SERIAL PRIMARY KEY (auto increment, unique)
    - group_id: VARCHAR NOT NULL UNIQUE
    - platform_type: VARCHAR NOT NULL
    - created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    - updated_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS split_bot_chat_whitelist (
                    id SERIAL PRIMARY KEY,
                    group_id VARCHAR NOT NULL UNIQUE,
                    platform_type VARCHAR NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITHOUT TIME ZONE NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("Table split_bot_chat_whitelist initialized/verified")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error initializing table: {str(e)}")
        raise


# CRUD Functions

def create_whitelisted_chat(
    group_id: str,
    platform_type: str
) -> WhitelistedChat:
    """
    Create a new whitelisted chat.
    
    Args:
        group_id: The chat's group_id (required, must be unique)
        platform_type: The platform type (required, must be "WHATSAPP" or "TELEGRAM")
    
    Returns:
        WhitelistedChat: The created whitelisted chat object
    
    Raises:
        UniqueViolation: If group_id already exists
        ValueError: If required fields are missing or platform_type is invalid
    """
    if not group_id or not platform_type:
        raise ValueError("group_id and platform_type are required fields")
    
    platform_type = platform_type.strip().upper()
    if platform_type not in ["WHATSAPP", "TELEGRAM"]:
        raise ValueError(f"platform_type must be either 'WHATSAPP' or 'TELEGRAM', got '{platform_type}'")
    
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO split_bot_chat_whitelist (group_id, platform_type, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id, group_id, platform_type, created_at, updated_at
                """,
                (
                    group_id.strip(),
                    platform_type,
                    datetime.now(),
                    datetime.now()
                )
            )
            row = cur.fetchone()
            conn.commit()
            whitelisted_chat = _row_to_whitelisted_chat(row)
            logger.info(f"Created whitelisted chat: {whitelisted_chat}")
            return whitelisted_chat
    except UniqueViolation as e:
        conn.rollback()
        logger.error(f"Error creating whitelisted chat: {str(e)}")
        raise
    except Exception as e:
        conn.rollback()
        logger.error(f"Unexpected error creating whitelisted chat: {str(e)}")
        raise


# Read Functions

def get_all_whitelisted_chats(limit: Optional[int] = None, offset: int = 0) -> List[WhitelistedChat]:
    """
    Get all whitelisted chats.
    
    Args:
        limit: Maximum number of chats to return (optional)
        offset: Number of chats to skip (default: 0)
    
    Returns:
        List[WhitelistedChat]: List of whitelisted chat objects
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT id, group_id, platform_type, created_at, updated_at
                FROM split_bot_chat_whitelist
                ORDER BY id
                OFFSET %s
            """
            params = [offset]
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            cur.execute(query, params)
            rows = cur.fetchall()
            return [_row_to_whitelisted_chat(row) for row in rows]
    except Exception as e:
        logger.error(f"Error getting all whitelisted chats: {str(e)}")
        raise


def search_whitelisted_chat(
    group_id: Optional[str] = None,
    platform_type: Optional[str] = None
) -> List[WhitelistedChat]:
    """
    Search for whitelisted chats by group_id and/or platform_type (exact matching).
    Both parameters are optional, but at least one should be provided for meaningful results.
    Uses AND logic - matches chats that satisfy all provided criteria.
    
    Args:
        group_id: Exact group_id match (optional)
        platform_type: Exact platform_type match (optional)
    
    Returns:
        List[WhitelistedChat]: List of matching whitelisted chat objects (empty list if no matches)
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT id, group_id, platform_type, created_at, updated_at
                FROM split_bot_chat_whitelist
                WHERE 1=1
            """
            params = []
            
            if group_id:
                query += " AND group_id = %s"
                params.append(group_id.strip())
            if platform_type:
                query += " AND platform_type = %s"
                params.append(platform_type.strip())
            
            cur.execute(query, params)
            rows = cur.fetchall()
            return [_row_to_whitelisted_chat(row) for row in rows]
    except Exception as e:
        logger.error(f"Error searching whitelisted chats: {str(e)}")
        raise


def get_whitelisted_chat_by_id(chat_id: int) -> Optional[WhitelistedChat]:
    """
    Get a whitelisted chat by its ID.
    
    Args:
        chat_id: The ID of the whitelisted chat
    
    Returns:
        Optional[WhitelistedChat]: The whitelisted chat object if found, None otherwise
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, group_id, platform_type, created_at, updated_at
                FROM split_bot_chat_whitelist
                WHERE id = %s
                """,
                (chat_id,)
            )
            row = cur.fetchone()
            if row:
                return _row_to_whitelisted_chat(row)
            return None
    except Exception as e:
        logger.error(f"Error getting whitelisted chat by id: {str(e)}")
        raise


def delete_whitelisted_chat(chat_id: int) -> bool:
    """
    Delete a whitelisted chat by its ID.
    
    Args:
        chat_id: The ID of the whitelisted chat to delete
    
    Returns:
        bool: True if the chat was deleted, False if it didn't exist
    """
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM split_bot_chat_whitelist
                WHERE id = %s
                """,
                (chat_id,)
            )
            deleted_count = cur.rowcount
            conn.commit()
            if deleted_count > 0:
                logger.info(f"Deleted whitelisted chat with id: {chat_id}")
                return True
            return False
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting whitelisted chat: {str(e)}")
        raise
