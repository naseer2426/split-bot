#!/usr/bin/env python3
"""
Command-line utility to add a chat to the whitelist.
Usage: python whitelist_chat_utility.py <group_id> <platform_type>
"""

import sys
import logging
import argparse
from db import connect_db, close_db
from chat_whitelist import create_whitelisted_chat, init_chat_whitelist_table

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Valid platform types
VALID_PLATFORM_TYPES = ["WHATSAPP", "TELEGRAM"]


def validate_platform_type(platform_type: str) -> str:
    """
    Validate that platform_type is one of the allowed values.
    
    Args:
        platform_type: The platform type to validate
    
    Returns:
        str: The validated platform type (uppercase)
    
    Raises:
        ValueError: If platform_type is not valid
    """
    platform_type = platform_type.strip().upper()
    if platform_type not in VALID_PLATFORM_TYPES:
        raise ValueError(
            f"Invalid platform_type '{platform_type}'. "
            f"Must be one of: {', '.join(VALID_PLATFORM_TYPES)}"
        )
    return platform_type


def main():
    """Main function to handle CLI arguments and create whitelisted chat."""
    parser = argparse.ArgumentParser(
        description="Add a chat to the whitelist",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python whitelist_chat_utility.py "group123" "WHATSAPP"
  python whitelist_chat_utility.py "group456" "TELEGRAM"

Valid platform types: {', '.join(VALID_PLATFORM_TYPES)}
        """
    )
    
    parser.add_argument(
        "group_id",
        type=str,
        help="The group ID to whitelist"
    )
    
    parser.add_argument(
        "platform_type",
        type=str,
        choices=VALID_PLATFORM_TYPES,
        help=f"Platform type (must be one of: {', '.join(VALID_PLATFORM_TYPES)})"
    )
    
    args = parser.parse_args()
    
    # Validate platform type (argparse handles this, but we'll validate again for safety)
    try:
        platform_type = validate_platform_type(args.platform_type)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    # Connect to database
    try:
        connect_db()
        logger.info("Connected to database")
        
        # Initialize table if it doesn't exist
        init_chat_whitelist_table()
        
        # Create whitelisted chat
        try:
            whitelisted_chat = create_whitelisted_chat(
                group_id=args.group_id,
                platform_type=platform_type
            )
            logger.info(f"Successfully created whitelisted chat: {whitelisted_chat}")
            print(f"✓ Successfully whitelisted chat:")
            print(f"  ID: {whitelisted_chat.id}")
            print(f"  Group ID: {whitelisted_chat.group_id}")
            print(f"  Platform Type: {whitelisted_chat.platform_type}")
            print(f"  Created At: {whitelisted_chat.created_at}")
            
        except ValueError as e:
            logger.error(f"Validation error: {str(e)}")
            print(f"✗ Error: {str(e)}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Error creating whitelisted chat: {str(e)}", exc_info=True)
            print(f"✗ Error creating whitelisted chat: {str(e)}")
            sys.exit(1)
        finally:
            close_db()
            logger.info("Closed database connection")
    
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}", exc_info=True)
        print(f"✗ Database connection error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
