import os
import httpx
from typing import Optional

logger = None

def set_logger(logger_instance):
    """Set the logger instance for OCR module."""
    global logger
    logger = logger_instance

async def process_image_with_mistral_ocr(image_url: str) -> Optional[str]:
    """
    Process an image using Mistral OCR API and return the extracted text.
    
    Args:
        image_url: The URL of the image to process.
        
    Returns:
        The extracted text (markdown) from the image, or None if there was an error.
    """
    if logger:
        logger.info(f"Processing image URL with Mistral OCR: {image_url}")
    
    # Retrieve the Mistral API key from environment variables
    api_key = os.getenv('MISTRAL_API_KEY')
    if not api_key:
        error_msg = "MISTRAL_API_KEY is not set in environment variables."
        if logger:
            logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Prepare the request payload according to Mistral OCR API structure
    payload = {
        "model": "mistral-ocr-latest",
        "document": {
            "type": "image_url",
            "image_url": image_url
        },
        "include_image_base64": False
    }
    
    # Set up the request headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    
    # Send the request to Mistral OCR API using httpx (async)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                'https://api.mistral.ai/v1/ocr',
                headers=headers,
                json=payload
            )
            
            # Handle different status codes
            if response.status_code == 200:
                result = response.json()
                if logger:
                    logger.info(f"ocr result {result}") 
                # Extract markdown from the first page
                pages = result.get('pages', [])
                if len(pages) != 1:
                    error_msg = f"Expected exactly 1 page, got {len(pages)}"
                    if logger:
                        logger.error(error_msg)
                    return f"Error: {error_msg}"
                
                markdown_text = pages[0].get('markdown', 'No text extracted.')
                if logger:
                    logger.info("OCR processing successful")
                return markdown_text
                
            elif response.status_code == 422:  # Validation error
                try:
                    validation_error = response.json()
                    detail = validation_error.get('detail', [])
                    if len(detail) > 0:
                        error_msg = f"Validation error: {detail[0].get('msg', 'Unknown validation error')}"
                    else:
                        error_msg = "Validation error: unknown validation error"
                except Exception:
                    error_msg = f"Validation error: {response.text}"
                
                if logger:
                    logger.error(error_msg)
                return f"Error: {error_msg}"
            else:
                error_msg = f"OCR API error: {response.status_code} - {response.text}"
                if logger:
                    logger.error(error_msg)
                return f"Error: {error_msg}"
                
    except httpx.TimeoutException:
        error_msg = "OCR request timed out"
        if logger:
            logger.error(error_msg)
        return "Error: Request timed out. Please try again."
    except Exception as e:
        error_msg = f"OCR processing failed: {str(e)}"
        if logger:
            logger.error(error_msg)
        return f"Error: {error_msg}"

