import os
import logging
from dotenv import load_dotenv
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ocr import process_image_with_mistral_ocr, set_logger
from ai import process_message

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

# Set logger for OCR module
set_logger(logger)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming images and file attachments, performing OCR."""
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
    
    # Send a "processing" message
    processing_msg = await update.message.reply_text("Processing image with OCR...")
    
    try:
        # Get the file object to retrieve the image URL
        logger.info(f"Fetching file path for - {file_id}")
        file = await context.bot.get_file(file_id)
        
        # Check if file_path exists
        if not file.file_path:
            raise ValueError("File path is None - cannot construct image URL")
        
        # file.file_path already contains the full URL, use it directly
        image_url = file.file_path
        
        # Process the image with OCR using the URL
        extracted_text = await process_image_with_mistral_ocr(image_url)
        
        # Delete the processing message and send the result
        await processing_msg.delete()
        
        if extracted_text:
            await update.message.reply_text(extracted_text)
        else:
            await update.message.reply_text("Sorry, I couldn't extract any text from the image.")
            
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        await processing_msg.delete()
        await update.message.reply_text(f"Error processing image: {str(e)}")

async def handle_by_ai(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages by processing them with AI."""
    if not update.message or not update.message.text:
        return
    
    # Send a "processing" message
    processing_msg = await update.message.reply_text("Processing with AI...")
    
    try:
        # Process the message with AI
        ai_response = process_message(update.message.text)
        
        # Delete the processing message and send the AI response
        await processing_msg.delete()
        await update.message.reply_text(ai_response)
        
    except Exception as e:
        logger.error(f"Error processing message with AI: {str(e)}")
        await processing_msg.delete()
        await update.message.reply_text(f"Error processing message: {str(e)}")

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        print("Error: TELEGRAM_BOT_TOKEN not found. Please set it in .env file.")
        return

    application = Application.builder().token(token).build()

    # Handle images and file attachments with OCR (add before text handler so images are processed first)
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))
    
    # Handle text messages - process with AI
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_by_ai))

    # Run the bot based on environment
    if IS_PROD:
        # Production mode: use webhook
        webhook_url = os.getenv("BOT_WEBHOOK")
        port = os.getenv("PORT")
        
        if not webhook_url:
            logger.error("BOT_WEBHOOK not found in environment variables for production mode.")
            return
        
        if not port:
            logger.error("PORT not found in environment variables for production mode.")
            return
        
        try:
            port = int(port)
        except ValueError:
            logger.error(f"Invalid PORT value: {port}. Must be an integer.")
            return
        
        logger.info(f"Starting bot in production mode with webhook: {webhook_url} on port {port}")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="/webhook",
            webhook_url=webhook_url,
            allowed_updates=Update.ALL_TYPES
        )
    else:
        # Development mode: use polling
        logger.info("Starting bot in development mode with polling")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
