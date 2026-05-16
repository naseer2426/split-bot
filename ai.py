import os
import logging
import time
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
from whatsapp_poll.tools import create_whatsapp_poll, get_whatsapp_poll_status
from ocr import ocr_image_url, ocr_image_base64, set_logger
from metrics import ai_processing_duration_seconds, ai_processing_total, ai_processing_errors_total

logger = logging.getLogger(__name__)

# Set logger for OCR module
set_logger(logger)

# System prompt for the AI
SYSTEM_PROMPT = '''You are Split. You help users split dinner bills in a group chat. The WhatsApp group_id for this chat is <GROUP_ID> (pass this exact value as group_id to create_whatsapp_poll). Follow the workflow below.

1. Bill image: The user sends a bill image; an OCR tool turns it into markdown you receive. Respond as though you read the bill yourself. If it does not look like a bill, apologise and ask for a clearer photo. If the bill is not in English, translate it; ask which language it is if unclear. When guiding the group, remind users to @<BOT_NAME> when addressing you.

2. WhatsApp poll for who ate what: Do not chase item assignments only through chat messages. After you have usable line items from the bill, call create_whatsapp_poll with a short title (what the poll is for), group_id="<GROUP_ID>", and options_json (a JSON array string of option labels).
   - Each array entry is one poll choice. Prefix every choice with its number as text inside the string, e.g. "1. Margherita Pizza $18", "2. Margherita Pizza $18" when quantity is two (see next bullet).
   - If the bill shows quantity 2 (or more) of the same item, use that many separate poll options — do not collapse them into one option with qty 2.

3. Updating the poll: If users ask to add, remove, merge, or reword poll choices, build the new option list and call create_whatsapp_poll again. Always treat the most recently created poll as authoritative: remember the latest poll_id from the tool response and use that poll_id when calling get_whatsapp_poll_status. 

4. When to load votes:
   - If users say they are done voting, or ask you to split / calculate, call get_whatsapp_poll_status using the latest poll_id first.
   - If users try to assign items manually before or instead of relying on votes, still call get_whatsapp_poll_status first to merge poll results with chat instructions. Make sure you call get_whatsapp_poll_status for every modification message. If there is a conflict, flag it out and confirm the real situation with the users.

5. Completing assignments: Map poll selections (who chose which numbered option) to people and items. The API omits options with zero votes — if after get_whatsapp_poll_status some bill line items still have nobody assigned, list those unassigned items and ask who ate them; users may reply by option number or by food name. Repeat until every item has an owner (or explicit split among people).

6. Splitting totals: ALWAYS use the calculator tool for every numeric step — never do arithmetic yourself. Allocate tax so each person owes their food subtotal plus a share of tax proportional to their share of taxable food (mirror the bill: if tax applies to specific lines, align with that; otherwise apportion bill tax by each person's share of relevant subtotals). After computing per-person totals, use the calculator again to verify the sum matches the bill total (within rounding).

7. Final message: Send the breakdown in this shape:
"{Restaurant name if known} Bill Split
- @username owes {amount}
    - Item (their share)
..."

8. Splitwise: Ask who paid for the bill. Put the step 7 breakdown in add_expense's details field; use participants' @usernames correctly. Respond with expense id and title. You can update/delete an expense if needed.

If conversation skips steps, state what you need next. Users may rarely ask only to record a Splitwise expense with everything already settled — then you may call add_expense directly.

Stay succinct.
'''

MAX_HISTORY_MESSAGES = 100

class SplitBotRequest:
    def __init__(self, message: str, group_id: str, sender: str, platform_type: str, image_url: Optional[str] = None, image_base64: Optional[Any] = None, bot_name: str = "me"):
        self.message = message
        self.group_id = group_id
        self.sender = sender
        self.platform_type = platform_type
        self.image_url = image_url
        self.image_base64 = image_base64
        self.bot_name = bot_name
    
    async def to_user_message(self) -> str:
        message = f"(Username:{self.sender}): {self.message}"
        
        # Process OCR if image_base64 is provided (priority over image_url)
        if self.image_base64:
            logger.info(f"Processing OCR for base64 image")
            ocr_text = await ocr_image_base64(self.image_base64.data, self.image_base64.mtype)
            if not ocr_text or ocr_text.startswith("Error:"):
                # Raise exception if OCR failed - will be caught in process_message
                raise ValueError(ocr_text if ocr_text else "Sorry, I couldn't extract any text from the image.")
            message += f"\n\nOCR Image Text: {ocr_text}"
        # Process OCR if image_url is provided
        elif self.image_url:
            logger.info(f"Processing OCR for image URL: {self.image_url}")
            ocr_text = await ocr_image_url(self.image_url)
            if not ocr_text or ocr_text.startswith("Error:"):
                # Raise exception if OCR failed - will be caught in process_message
                raise ValueError(ocr_text if ocr_text else "Sorry, I couldn't extract any text from the image.")
            message += f"\n\nOCR Image Text: {ocr_text}"
        
        return message
    
def get_system_prompt(bot_name: str, group_id: str) -> str:
    return SYSTEM_PROMPT.replace("<BOT_NAME>", bot_name).replace("<GROUP_ID>", group_id)

async def process_message(request: SplitBotRequest) -> str:
    """
    Process a message using Grok 4 Fast via OpenRouter with conversation memory stored in PostgreSQL.
    Uses LangChain agents with a calculator tool and checkpoint-based memory.
    
    Args:
        request: SplitBotRequest object containing message, group_id, sender, platform_type, and optionally image_url
        
    Returns:
        The AI's response as a string
    """
    platform_type = request.platform_type.strip().upper()
    start_time = time.time()
    
    # Get user message (OCR processing happens inside to_user_message)
    try:
        user_message = await request.to_user_message()
    except ValueError as e:
        # Return error message if OCR failed
        duration = time.time() - start_time
        ai_processing_duration_seconds.labels(platform_type=platform_type).observe(duration)
        ai_processing_total.labels(platform_type=platform_type, status="failure").inc()
        ai_processing_errors_total.labels(platform_type=platform_type, error_type="OCRError").inc()
        return str(e)
    
    # Get environment variables
    base_url = os.getenv("AI_BASE_URL")
    api_token = os.getenv("AI_TOKEN")
    db_connection_string = os.getenv("DB_CONNECTION_STRING")

    if not base_url:
        error = ValueError("AI_BASE_URL environment variable is required")
        duration = time.time() - start_time
        ai_processing_duration_seconds.labels(platform_type=platform_type).observe(duration)
        ai_processing_total.labels(platform_type=platform_type, status="failure").inc()
        ai_processing_errors_total.labels(platform_type=platform_type, error_type="ConfigurationError").inc()
        raise error
    
    if not api_token:
        error = ValueError("AI_TOKEN environment variable is required")
        duration = time.time() - start_time
        ai_processing_duration_seconds.labels(platform_type=platform_type).observe(duration)
        ai_processing_total.labels(platform_type=platform_type, status="failure").inc()
        ai_processing_errors_total.labels(platform_type=platform_type, error_type="ConfigurationError").inc()
        raise error
    
    if not db_connection_string:
        logger.error("DB_CONNECTION_STRING not found in environment variables")
        error = ValueError("DB_CONNECTION_STRING environment variable is required")
        duration = time.time() - start_time
        ai_processing_duration_seconds.labels(platform_type=platform_type).observe(duration)
        ai_processing_total.labels(platform_type=platform_type, status="failure").inc()
        ai_processing_errors_total.labels(platform_type=platform_type, error_type="ConfigurationError").inc()
        raise error
    
    try:
        # Initialize ChatOpenAI with OpenRouter configuration
        model = ChatOpenAI(
            model="x-ai/grok-4.3",
            base_url=base_url,
            api_key=api_token,
            temperature=0.7,
        )
        
        # Create agent with calculator tool, checkpointer, and trim_messages middleware
        tools = [calculator, add_expense, update_expense, delete_expense, create_whatsapp_poll, get_whatsapp_poll_status]
        
        # Use context manager to properly manage database connection
        with PostgresSaver.from_conn_string(db_connection_string) as checkpointer:
            checkpointer.setup()
            
            # Create agent within the context manager
            # Use bot_name from request to generate system prompt
            system_prompt_with_bot_name = get_system_prompt(request.bot_name, request.group_id)
            agent = create_agent(
                model, 
                tools, 
                system_prompt=system_prompt_with_bot_name,
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
            
            # Track successful processing
            duration = time.time() - start_time
            ai_processing_duration_seconds.labels(platform_type=platform_type).observe(duration)
            ai_processing_total.labels(platform_type=platform_type, status="success").inc()
            
            return ai_response
        
    except Exception as e:
        duration = time.time() - start_time
        ai_processing_duration_seconds.labels(platform_type=platform_type).observe(duration)
        ai_processing_total.labels(platform_type=platform_type, status="failure").inc()
        ai_processing_errors_total.labels(platform_type=platform_type, error_type=type(e).__name__).inc()
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
