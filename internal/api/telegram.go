package api

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"

	"github.com/gin-contrib/requestid"
	"github.com/gin-gonic/gin"
	"github.com/naseer2426/split-bot/internal/ocr"
	"github.com/naseer2426/split-bot/internal/splitbot"
	"github.com/naseer2426/split-bot/internal/telegram"
)

const (
	TelegramWebhookPath = "/telegram/webhook"
)

type TelegramWebhook struct {
	SplitBot    *splitbot.Bot
	TelegramAPI *telegram.TelegramAPI
	OCR         ocr.ImageOCR
}

func NewTelegramWebhook() *TelegramWebhook {
	tw := &TelegramWebhook{
		TelegramAPI: telegram.NewTelegramAPI(TelegramWebhookPath),
		SplitBot:    splitbot.NewBot(),
		OCR:         ocr.NewMistralOCR(),
	}
	return tw
}

func (t *TelegramWebhook) TelegramWebhook(c *gin.Context) {
	requestID := requestid.Get(c)
	message, chatID, err := t.preProcessMsg(c)
	if err != nil {
		log.Printf("create splitbot message failed %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": err.Error(),
		})
		return
	}

	if message == nil {
		c.JSON(http.StatusOK, gin.H{"status": "ignored"})
		return
	}

	response, err := t.SplitBot.HandleMessage(requestID, message)
	if err != nil {
		log.Printf("handle message failed %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": err.Error(),
		})
		return
	}

	if err := t.TelegramAPI.SendMessage(requestID, chatID, response); err != nil {
		log.Printf("telegram webhook: failed to send OCR result: %v", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "failed to send OCR result"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "ok"})
	return
}

func (t *TelegramWebhook) parseBody(c *gin.Context) (*telegram.Update, error) {
	// Parse the JSON manually
	var update telegram.Update
	bodyBytes, err := c.GetRawData()
	if err != nil {
		return nil, errors.New("failed to read body")
	}
	if err := json.Unmarshal(bodyBytes, &update); err != nil {
		return nil, errors.New(fmt.Sprintf("invalid payload - %s", string(bodyBytes)))
	}

	return &update, nil
}

func (t *TelegramWebhook) handlePhotoMessage(msg *splitbot.Message, photos []telegram.Photo, caption string, requestID string) error {
	highestResPhoto := photos[len(photos)-1]

	// Get the image URL
	url, err := t.TelegramAPI.GetImageUrl(requestID, highestResPhoto.FileID)
	if err != nil {
		return errors.New("failed to get image URL")
	}

	// Extract text from image using OCR
	extractedText, err := t.OCR.ExtractTextFromImage(requestID, url)
	if err != nil {
		log.Printf("OCR extraction failed for photo: %v", err)
		extractedText = "OCR extraction failed"
	}

	msg.Image = &splitbot.Image{
		FileID:        highestResPhoto.FileID,
		Url:           url,
		ExtractedText: extractedText,
	}
	if len(caption) > 0 {
		msg.Text = caption
	}
	return nil
}

func (t *TelegramWebhook) handleDocumentMessage(msg *splitbot.Message, document *telegram.Document, caption string, requestID string) error {
	// Get the image URL
	url, err := t.TelegramAPI.GetImageUrl(requestID, document.FileID)
	if err != nil {
		return errors.New("failed to get image URL")
	}

	// Extract text from image using OCR
	extractedText, err := t.OCR.ExtractTextFromImage(requestID, url)
	if err != nil {
		log.Printf("OCR extraction failed for document: %v", err)
		extractedText = "OCR extraction failed"
	}

	msg.Image = &splitbot.Image{
		FileID:        document.FileID,
		Url:           url,
		ExtractedText: extractedText,
	}
	if len(caption) > 0 {
		msg.Text = caption
	}
	return nil
}

func (t *TelegramWebhook) preProcessMsg(c *gin.Context) (*splitbot.Message, int64, error) {
	update, err := t.parseBody(c)
	if err != nil {
		return nil, 0, err
	}
	if update.Message == nil {
		return nil, 0, nil
	}
	msg := &splitbot.Message{
		Text: update.Message.Text,
	}
	requestID := requestid.Get(c)
	if update.Message.From != nil {
		msg.From = splitbot.User{
			ID:       update.Message.From.ID,
			Username: update.Message.From.Username,
		}
	}
	if len(update.Message.Photo) > 0 {
		if err := t.handlePhotoMessage(msg, update.Message.Photo, update.Message.Caption, requestID); err != nil {
			return nil, 0, err
		}
		// the message can either contain image or document
		return msg, update.Message.Chat.ID, nil
	}
	if update.Message.Document != nil {
		if err := t.handleDocumentMessage(msg, update.Message.Document, update.Message.Caption, requestID); err != nil {
			return nil, 0, err
		}
		return msg, update.Message.Chat.ID, nil
	}
	return msg, update.Message.Chat.ID, nil
}
