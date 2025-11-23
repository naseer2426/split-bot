import os
import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)

def process_message(message: str) -> str:
    """
    Process a message using Grok 4 Fast via OpenRouter.
    
    Args:
        message: The input message string to process
        
    Returns:
        The AI's response as a string
    """
    # Get environment variables
    base_url = os.getenv("AI_BASE_URL")
    api_token = os.getenv("AI_TOKEN")
    
    if not base_url:
        logger.error("AI_BASE_URL not found in environment variables")
        raise ValueError("AI_BASE_URL environment variable is required")
    
    if not api_token:
        logger.error("AI_TOKEN not found in environment variables")
        raise ValueError("AI_TOKEN environment variable is required")
    
    try:
        # Initialize ChatOpenAI with OpenRouter configuration
        # OpenRouter is compatible with OpenAI's API format
        llm = ChatOpenAI(
            model="x-ai/grok-4-fast",  # Grok 4 Fast model via OpenRouter
            base_url=base_url,
            api_key=api_token,
            temperature=0.7,
        )
        
        # Create a human message and get response
        messages = [HumanMessage(content=message)]
        response = llm.invoke(messages)
        
        return response.content
        
    except Exception as e:
        logger.error(f"Error processing message with AI: {str(e)}")
        raise

