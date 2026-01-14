import logging
import os
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional
from contextlib import asynccontextmanager
from ai import process_message, SplitBotRequest
from db import connect_db, close_db
from dotenv import load_dotenv
from chat_whitelist import init_chat_whitelist_table, search_whitelisted_chat
from splitwise.users import init_users_table

# Load environment variables
load_dotenv()

# Determine environment
ENV = os.getenv("ENV", "development").lower()
IS_DEV = ENV in ["dev", "development"]
IS_PROD = ENV in ["prod", "production"]

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.DEBUG if IS_DEV else logging.INFO
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan: startup and shutdown events."""
    # Startup: Connect to database
    try:
        connect_db()
        logger.info("Database connection established on startup")
        init_users_table()
        init_chat_whitelist_table()
    except Exception as e:
        logger.error(f"Failed to connect to database on startup: {str(e)}")
        raise
    
    yield
    
    # Shutdown: Close database connection
    try:
        close_db()
        logger.info("Database connection closed on shutdown")
    except Exception as e:
        logger.error(f"Error closing database connection on shutdown: {str(e)}")


app = FastAPI(
    title="Split Bot API",
    version="1.0.0",
    lifespan=lifespan
)


class ProcessMessageRequest(BaseModel):
    """Pydantic model for request validation matching SplitBotRequest"""
    message: str = Field(..., description="The message content")
    group_id: str = Field(..., description="The group ID for conversation context")
    sender: str = Field(..., description="The sender ID")
    platform_type: str = Field(..., description="Platform type (WHATSAPP or TELEGRAM)")
    image_url: Optional[str] = Field(None, description="Optional URL to an image for OCR processing")


class ProcessMessageResponse(BaseModel):
    """Response model for the process_message endpoint"""
    response: Optional[str] = Field(None, description="The AI response message")
    error: Optional[str] = Field(None, description="Error message if any")


def check_group_whitelisted(group_id: str, platform_type: str) -> bool:
    """
    Check if a group_id is whitelisted for the given platform_type.
    
    Args:
        group_id: The group ID to check
        platform_type: The platform type (WHATSAPP or TELEGRAM)
    
    Returns:
        bool: True if the group is whitelisted, False otherwise
    """
    try:
        platform_type = platform_type.strip().upper()
        results = search_whitelisted_chat(
            group_id=group_id.strip(),
            platform_type=platform_type
        )
        return len(results) > 0
    except Exception as e:
        logger.error(f"Error checking whitelist: {str(e)}")
        return False


@app.post("/process_message", response_model=ProcessMessageResponse)
async def process_message_endpoint(request: ProcessMessageRequest) -> ProcessMessageResponse:
    """
    Process a message using the Split Bot AI.
    
    Accepts a JSON body with message, group_id, sender, platform_type, and optional image_url.
    Returns the AI's response or an error message.
    """
    try:
        # Check if group is whitelisted
        if not check_group_whitelisted(request.group_id, request.platform_type):
            not_allowed_resp = f"This chat with ID: {request.group_id}, is not whitelisted, please ask Naseer to whitelist it"
            logger.warning(f"Group {request.group_id} on platform {request.platform_type} is not whitelisted")
            return ProcessMessageResponse(
                response=not_allowed_resp,
                error=None
            )
        
        # Convert Pydantic model to SplitBotRequest
        split_bot_request = SplitBotRequest(
            message=request.message,
            group_id=request.group_id,
            sender=request.sender,
            image_url=request.image_url
        )
        
        # Process the message
        ai_response = await process_message(split_bot_request)
        
        return ProcessMessageResponse(
            response=ai_response,
            error=None
        )
    
    except ValueError as e:
        # Handle validation errors (e.g., OCR failures)
        logger.error(f"ValueError in process_message: {str(e)}")
        return ProcessMessageResponse(
            response=None,
            error=str(e)
        )
    
    except Exception as e:
        # Handle any other unexpected errors
        logger.error(f"Unexpected error in process_message: {str(e)}", exc_info=True)
        return ProcessMessageResponse(
            response=None,
            error=f"Internal server error: {str(e)}"
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
