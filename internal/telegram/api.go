package telegram

import (
	"fmt"

	"github.com/go-resty/resty/v2"
)

type TelegramAPI struct {
	token  string
	client *resty.Client
}

func NewTelegramAPI(token string) *TelegramAPI {
	return &TelegramAPI{
		token:  token,
		client: resty.New(),
	}
}

// SendMessage sends a message to a Telegram chat
func (t *TelegramAPI) SendMessage(requestID string, chatID int64, text string) error {
	token := t.token
	if token == "" {
		return fmt.Errorf("TELEGRAM_BOT_TOKEN is not set")
	}

	reply := SendMessageRequest{
		ChatID: chatID,
		Text:   text,
	}

	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", token)
	resp, err := t.client.R().
		SetHeader("Content-Type", "application/json").
		SetHeader("X-Request-ID", requestID).
		SetBody(reply).
		Post(url)

	if err != nil {
		return fmt.Errorf("http call to telegram failed: %w", err)
	}

	if resp.StatusCode() < 200 || resp.StatusCode() >= 300 {
		return fmt.Errorf("telegram returned non-2xx status: %d", resp.StatusCode())
	}

	return nil
}

// GetImageUrl retrieves the URL for accessing an image file by its file_unique_id
func (t *TelegramAPI) GetImageUrl(requestID, fileId string) (string, error) {
	token := t.token
	if token == "" {
		return "", fmt.Errorf("TELEGRAM_BOT_TOKEN is not set")
	}

	// First, we need to get the file info using getFile API
	url := fmt.Sprintf("https://api.telegram.org/bot%s/getFile?file_id=%s", token, fileId)

	var fileResponse struct {
		OK     bool `json:"ok"`
		Result struct {
			FilePath string `json:"file_path"`
		} `json:"result"`
	}

	resp, err := t.client.R().
		SetDebug(true).
		SetResult(&fileResponse).
		Get(url)

	if err != nil {
		return "", fmt.Errorf("failed to get file info: %w", err)
	}

	if resp.StatusCode() < 200 || resp.StatusCode() >= 300 {
		return "", fmt.Errorf("telegram getFile returned non-2xx status: %d", resp.StatusCode())
	}

	if !fileResponse.OK {
		return "", fmt.Errorf("telegram API returned error for file_id: %s", fileId)
	}

	// Construct the full URL to access the file
	imageURL := fmt.Sprintf("https://api.telegram.org/file/bot%s/%s", token, fileResponse.Result.FilePath)

	return imageURL, nil
}
