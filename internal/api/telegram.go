package api

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
)

type telegramUpdate struct {
	UpdateID int              `json:"update_id"`
	Message  *telegramMessage `json:"message"`
}

type telegramMessage struct {
	MessageID int           `json:"message_id"`
	Text      string        `json:"text"`
	Chat      telegramChat  `json:"chat"`
	From      *telegramUser `json:"from"`
	Date      int64         `json:"date"`
}

type telegramChat struct {
	ID   int64  `json:"id"`
	Type string `json:"type"`
}

type telegramUser struct {
	ID           int64  `json:"id"`
	IsBot        bool   `json:"is_bot"`
	FirstName    string `json:"first_name"`
	Username     string `json:"username"`
	LanguageCode string `json:"language_code"`
}

type sendMessageRequest struct {
	ChatID int64  `json:"chat_id"`
	Text   string `json:"text"`
}

func TelegramWebhook(c *gin.Context) {
	var update telegramUpdate
	if err := c.ShouldBindJSON(&update); err != nil {
		log.Printf("telegram webhook: failed to bind json: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid payload"})
		return
	}

	if update.Message == nil || update.Message.Text == "" {
		c.JSON(http.StatusOK, gin.H{"status": "ignored"})
		return
	}

	token := os.Getenv("TELEGRAM_BOT_TOKEN")
	if token == "" {
		log.Printf("telegram webhook: TELEGRAM_BOT_TOKEN is not set")
		c.JSON(http.StatusInternalServerError, gin.H{"error": "missing TELEGRAM_BOT_TOKEN"})
		return
	}

	reply := sendMessageRequest{
		ChatID: update.Message.Chat.ID,
		Text:   update.Message.Text,
	}

	payload, err := json.Marshal(reply)
	if err != nil {
		log.Printf("telegram webhook: failed to marshal reply: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to marshal reply"})
		return
	}

	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", token)
	req, err := http.NewRequest(http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		log.Printf("telegram webhook: failed to create http request: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "failed to create request"})
		return
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		log.Printf("telegram webhook: http call to telegram failed: %v", err)
		c.JSON(http.StatusBadGateway, gin.H{"error": "failed to call telegram"})
		return
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		log.Printf("telegram webhook: telegram returned non-2xx status: %d", resp.StatusCode)
		c.JSON(http.StatusBadGateway, gin.H{"error": "telegram returned non-2xx"})
		return
	}

	c.JSON(http.StatusOK, gin.H{"status": "ok"})
}
