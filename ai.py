import os
import logging
from typing import Any
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import before_model
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.runtime import Runtime

logger = logging.getLogger(__name__)

# System prompt for the AI
SYSTEM_PROMPT = "You are a helpful assistant. You provide clear, concise, and accurate responses to user queries."


@before_model
def trim_messages(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """
    Keep only the last few messages to fit context window.
    Configurable via the max_messages parameter (default: 10 message pairs = 20 messages).
    """
    messages = state["messages"]

    print(messages)
    # Get max_messages from config, default to 20 (10 pairs of human+ai messages)
    max_messages = 20
    
    if len(messages) <= max_messages:
        return None  # No changes needed
    
    # Keep the first message (usually system prompt) and last N messages
    recent_messages = messages[-max_messages:]
    
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



def process_message(
    message: str,
    group_id: str,
) -> str:
    """
    Process a message using Grok 4 Fast via OpenRouter with conversation memory stored in PostgreSQL.
    Uses LangChain agents with a calculator tool and checkpoint-based memory.
    
    Args:
        message: The input message string to process
        group_id: Unique identifier for the group/chat as a string (used as thread_id for conversation memory)
        max_messages: Maximum number of messages to keep in context (default: 20)
        
    Returns:
        The AI's response as a string
    """
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
        tools = [calculator]
        
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
                {"messages": [{"role": "user", "content": message}]},
                {
                    "configurable": {
                        "thread_id": group_id,
                    }
                }
            )
            
            # Extract the AI response from the last message
            ai_response = result["messages"][-1].content
            
            return ai_response
        
    except Exception as e:
        logger.error(f"Error processing message with AI: {str(e)}")
        raise
