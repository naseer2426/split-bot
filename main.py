import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from ai import process_message, SplitBotRequest

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

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming images and file attachments, performing OCR and processing with AI."""
    if not update.message:
        return
    
    # Determine if it's a photo or document
    file_id = None
    if update.message.photo:
        # Get the largest photo size
        photo = update.message.photo[-1]
        file_id = photo.file_id
    elif update.message.document:
        # Handle file attachments (documents)
        document = update.message.document
        file_id = document.file_id
    else:
        return
    
    # Get group/chat ID (works for both groups and private chats)
    group_id = str(update.message.chat.id)
    
    # Extract sender information
    from_user = update.message.from_user
    sender = from_user.username
    
    # Send a "processing" message
    processing_msg = await update.message.reply_text("Processing with AI...")
    
    try:
        # Get the file object to retrieve the image URL
        logger.info(f"Fetching file path for - {file_id}")
        file = await context.bot.get_file(file_id)
        
        # Check if file_path exists
        if not file.file_path:
            raise ValueError("File path is None - cannot construct image URL")
        
        # file.file_path already contains the full URL, use it directly
        image_url = file.file_path
        
        # Create SplitBotRequest object with image URL
        request = SplitBotRequest(
            message="",  # Empty message for image-only requests
            group_id=group_id,
            sender=sender,
            image_url=image_url
        )
        
        # Process the image with AI (OCR is handled internally)
        ai_response = await process_message(request)
        
        # Delete the processing message and send the AI response
        await processing_msg.delete()
        await update.message.reply_text(ai_response)
            
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        await processing_msg.delete()
        await update.message.reply_text(f"Error processing image: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages by processing them with AI."""
    if not update.message or not update.message.text:
        return
    
    # Get group/chat ID (works for both groups and private chats)
    group_id = str(update.message.chat.id)
    
    # Extract sender information
    from_user = update.message.from_user
    sender = from_user.username
    
    # Send a "processing" message
    processing_msg = await update.message.reply_text("Processing with AI...")
    
    try:
        # Create SplitBotRequest object
        request = SplitBotRequest(
            message=update.message.text,
            group_id=group_id,
            sender=sender
        )
        
        # Process the message with AI (including conversation history)
        ai_response = await process_message(request)
        
        # Delete the processing message and send the AI response
        await processing_msg.delete()
        await update.message.reply_text(ai_response)
        
    except Exception as e:
        logger.error(f"Error processing message with AI: {str(e)}")
        await processing_msg.delete()
        await update.message.reply_text(f"Error processing message: {str(e)}")

def setup_application() -> Application:
    """Setup the Telegram bot application with handlers."""
    # Create the Application and pass it your bot's token.
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        print("Error: TELEGRAM_BOT_TOKEN not found. Please set it in .env file.")
        raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

    application = Application.builder().token(token).build()

    # Handle images and file attachments with OCR (add before text handler so images are processed first)
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))
    
    # Handle text messages - process with AI
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return application

def setup_prod_webhook(application: Application) -> None:
    """Setup and run the bot in production mode with webhook."""
    webhook_url = os.getenv("BOT_WEBHOOK")
    port = os.getenv("PORT")
    
    if not webhook_url:
        logger.error("BOT_WEBHOOK not found in environment variables for production mode.")
        raise ValueError("BOT_WEBHOOK not found in environment variables for production mode")
    
    if not port:
        logger.error("PORT not found in environment variables for production mode.")
        raise ValueError("PORT not found in environment variables for production mode")
    
    try:
        port = int(port)
    except ValueError:
        logger.error(f"Invalid PORT value: {port}. Must be an integer.")
        raise ValueError(f"Invalid PORT value: {port}. Must be an integer")
    
    logger.info(f"Starting bot in production mode with webhook: {webhook_url} on port {port}")
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="/webhook",
        webhook_url=webhook_url,
        allowed_updates=Update.ALL_TYPES
    )

def setup_non_prod_polling(application: Application) -> None:
    """Setup and run the bot in non-production mode with polling."""
    logger.info("Starting bot in development mode with polling")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

def main() -> None:
    """Start the bot."""
    try:
        application = setup_application()
        
        # Run the bot based on environment
        if IS_PROD:
            setup_prod_webhook(application)
        else:
            setup_non_prod_polling(application)
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        return

if __name__ == "__main__":
    main()
