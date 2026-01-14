import logging
import os
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional
from ai import process_message, SplitBotRequest
from dotenv import load_dotenv

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
app = FastAPI(title="Split Bot API", version="1.0.0")


class ProcessMessageRequest(BaseModel):
    """Pydantic model for request validation matching SplitBotRequest"""
    message: str = Field(..., description="The message content")
    group_id: str = Field(..., description="The group ID for conversation context")
    sender: str = Field(..., description="The sender ID")
    image_url: Optional[str] = Field(None, description="Optional URL to an image for OCR processing")


class ProcessMessageResponse(BaseModel):
    """Response model for the process_message endpoint"""
    response: Optional[str] = Field(None, description="The AI response message")
    error: Optional[str] = Field(None, description="Error message if any")


@app.post("/process_message", response_model=ProcessMessageResponse)
async def process_message_endpoint(request: ProcessMessageRequest) -> ProcessMessageResponse:
    """
    Process a message using the Split Bot AI.
    
    Accepts a JSON body with message, group_id, sender, and optional image_url.
    Returns the AI's response or an error message.
    """
    try:
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
