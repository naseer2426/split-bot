import os
import logging
from typing import Any, Optional
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import before_model
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.runtime import Runtime
from splitwise.tools import add_expense, update_expense, delete_expense
from ocr import process_image_with_mistral_ocr, set_logger

logger = logging.getLogger(__name__)

# Set logger for OCR module
set_logger(logger)

# System prompt for the AI
SYSTEM_PROMPT = '''You are Split. A helpful bot who's purpose is to help users split their dinner bills. You are part of a group chat where users will interact with you. Follow the steps below to help them split the bill

1. The user should send an image of a bill. This image will be parsed by an OCR tool into markdown which will be sent to you. The user does not know the details about this OCR tool so you need to respond as though you can "see and read the bill". If the markdown passed to you does not look like a bill, then its most likely not an image of a bill or an very unclear one. Apologise and ask the user to send another picture of the bill if this happens. If the parsed bill is in any language other than english, translate it to english. Ask the user what language it is in if it is unclear.
2. Confirm with the user that the markdown you received from the OCR tool is accurate. Return a message to the user in a list format where each item is like this "- {Item} (Qty {Quantity}) -> ${price}". Make sure you the user confirms the list is correct. There are cases where users may ask you to correct the list because the OCR result was inaccurate, make the appropriate changes and send them the new list. Keep doing this until user confirms. When you respond to the user make sure you remind them to @naseer_split_bot when they intend to talk to you
3. The user may directly tell who ate what or may just give you a list of people who were present for the dinner. You will need to find who ate what and do the splits. Every time someone tells you about an item they ate, return a list of unaccounted for items, the format should be like this
"Assigned so far
- Item Name (price) - split by {number} of people/person
    - Person 1 name (owes {price/n})
    - Person 2 name (owes {price/n})

Not yet assigned
- Item Name (price)
"
Make sure you handle items with > 1 quantity correctly. Again whenever you respond to the user make sure to remind the to @naseer_split_bot when they intend to talk to you
4. Now that you have all information you need to do the splits. Use the calculator to do all the maths, don't ever try to do math on your own!. Make sure you do the tax splits correctly based on what everyone ate. After you make the splits finally use the calculator tool to check that the sum of everyone's amount adds up to the total in the bill
5. Send a final list of people along with how much they owe in the format given below
"
{Restaurant Name from bill if you can find it} Bill Split

- username1 owes {amount they owe}
    - Item (price they owe)
- username1 owes {amount they owe}
"
6. Finally the user may choose to add the expense to Splitwise. You will need to know who paid for the bill. Make sure you put the information from step 5 into the details field of the add_expense tool. The sender_ids used in the add_expense tool are actually the @username of the user. So make sure you know the @username of the everyone involved in the bill. You also have the ability to update/delete the expense if you need to. Make sure you respond with the expense ID and expense title to the user.

If users don't naturally follow the steps described here, tell them what you require to move forward. Do note the user's may directly ask you to add an expense (for which they have all the details) to splitwise. In that case, you can use the add_expense tool directly.

Make sure your answers are succinct, don't be too verbose
'''

MAX_HISTORY_MESSAGES = 20

class SplitBotRequest:
    def __init__(self, message: str, group_id: str, sender: str, image_url: Optional[str] = None):
        self.message = message
        self.group_id = group_id
        self.sender = sender
        self.image_url = image_url
    
    async def to_user_message(self) -> str:
        message = f"(Sender ID:{self.sender}): {self.message}"
        
        # Process OCR if image_url is provided
        if self.image_url:
            logger.info(f"Processing OCR for image URL: {self.image_url}")
            ocr_text = await process_image_with_mistral_ocr(self.image_url)
            if not ocr_text or ocr_text.startswith("Error:"):
                # Raise exception if OCR failed - will be caught in process_message
                raise ValueError(ocr_text if ocr_text else "Sorry, I couldn't extract any text from the image.")
            message += f"\n\nOCR Image Text: {ocr_text}"
        
        return message

async def process_message(request: SplitBotRequest) -> str:
    """
    Process a message using Grok 4 Fast via OpenRouter with conversation memory stored in PostgreSQL.
    Uses LangChain agents with a calculator tool and checkpoint-based memory.
    
    Args:
        request: SplitBotRequest object containing message, group_id, sender, and optionally image_url
        
    Returns:
        The AI's response as a string
    """
    # Get user message (OCR processing happens inside to_user_message)
    try:
        user_message = await request.to_user_message()
    except ValueError as e:
        # Return error message if OCR failed
        return str(e)
    
    # Get environment variables
    base_url = os.getenv("AI_BASE_URL")
    api_token = os.getenv("AI_TOKEN")
    db_connection_string = os.getenv("DB_CONNECTION_STRING")
    
    if not base_url:
        raise ValueError("AI_BASE_URL environment variable is required")
    
    if not api_token:
        raise ValueError("AI_TOKEN environment variable is required")
    
    if not db_connection_string:
        logger.error("DB_CONNECTION_STRING not found in environment variables")
        raise ValueError("DB_CONNECTION_STRING environment variable is required")
    
    try:
        # Initialize ChatOpenAI with OpenRouter configuration
        model = ChatOpenAI(
            model="x-ai/grok-4-fast",
            base_url=base_url,
            api_key=api_token,
            temperature=0.7,
        )
        
        # Create agent with calculator tool, checkpointer, and trim_messages middleware
        tools = [calculator, add_expense, update_expense, delete_expense]
        
        # Use context manager to properly manage database connection
        with PostgresSaver.from_conn_string(db_connection_string) as checkpointer:
            checkpointer.setup()
            
            # Create agent within the context manager
            agent = create_agent(
                model, 
                tools, 
                system_prompt=SYSTEM_PROMPT,
                checkpointer=checkpointer,
                middleware=[trim_messages]
            )
            
            # Invoke agent with message and thread_id (group_id)
            # The checkpointer automatically handles message history persistence
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]},
                {
                    "configurable": {
                        "thread_id": request.group_id,
                    }
                }
            )
            
            # Extract the AI response from the last message
            ai_response = result["messages"][-1].content
            
            return ai_response
        
    except Exception as e:
        logger.error(f"Error processing message with AI: {str(e)}")
        raise


@before_model
def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """
    Keep only the last few messages to fit context window.
    Configurable via the max_messages parameter (default: 10 message pairs = 20 messages).
    """
    messages = state["messages"]

    
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return None  # No changes needed
    
    recent_messages = messages[-MAX_HISTORY_MESSAGES:]
    
    return {
        "messages": [
            RemoveMessage(id=REMOVE_ALL_MESSAGES),
            *recent_messages
        ]
    }


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression and return the result.
    
    Args:
        expression: A mathematical expression as a string (e.g., "2 + 2", "10 * 5", "100 / 4")
        
    Returns:
        The result of the calculation as a string
    """
    try:
        # Safely evaluate the mathematical expression
        # Only allow basic math operations and numbers
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return "Error: Invalid characters in expression. Only numbers and basic operators (+, -, *, /) are allowed."
        
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error calculating: {str(e)}"
