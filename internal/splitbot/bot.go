package splitbot

import (
	"os"

	"github.com/naseer2426/split-bot/internal/ocr"
)

type Bot struct {
	OCR ocr.ImageOCR
}

func NewBot() *Bot {
	return &Bot{
		OCR: ocr.NewMistralOCR(os.Getenv("MISTRAL_API_KEY")),
	}
}

func (b *Bot) HandleMessage(requestID string, message *Message) (string, error) {
	// If there's an image path, extract text using OCR
	if message.ImagePath != "" {
		// Use a simple request ID for now - you might want to generate a proper UUID
		extractedText, err := b.OCR.ExtractTextFromImage(requestID, message.ImagePath)
		if err != nil {
			return "", err
		}
		return extractedText, nil
	}

	// If no image path, return the text message
	return message.Text, nil
}
