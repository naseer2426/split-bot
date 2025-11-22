import os
import logging
from dotenv import load_dotenv
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from ocr import process_image_with_mistral_ocr, set_logger

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Set logger for OCR module
set_logger(logger)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming images and perform OCR."""
    if not update.message or not update.message.photo:
        return
    
    # Get the largest photo size
    photo = update.message.photo[-1]
    
    # Send a "processing" message
    processing_msg = await update.message.reply_text("Processing image with OCR...")
    
    try:
        # Get the file object to retrieve the image URL
        logger.info(f"Fetching file path for - {photo.file_id}")
        file = await context.bot.get_file(photo.file_id)
        
        # Check if file_path exists
        if not file.file_path:
            raise ValueError("File path is None - cannot construct image URL")
        
        # file.file_path already contains the full URL, use it directly
        image_url = file.file_path
        logger.info(f"Using image URL: {image_url}")
        
        # Process the image with OCR using the URL
        extracted_text = await process_image_with_mistral_ocr(image_url)
        
        # Delete the processing message and send the result
        await processing_msg.delete()
        
        if extracted_text:
            await update.message.reply_text(f"Extracted text:\n\n{extracted_text}")
        else:
            await update.message.reply_text("Sorry, I couldn't extract any text from the image.")
            
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        await processing_msg.delete()
        await update.message.reply_text(f"Error processing image: {str(e)}")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    await update.message.reply_text(update.message.text)

def main() -> None:
    """Start the bot."""
    # Create the Application and pass it your bot's token.
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("No TELEGRAM_BOT_TOKEN found in environment variables.")
        print("Error: TELEGRAM_BOT_TOKEN not found. Please set it in .env file.")
        return

    application = Application.builder().token(token).build()

    # Handle images with OCR (add before text handler so images are processed first)
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    
    # Handle text messages - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
