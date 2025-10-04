package ocr

import (
	"encoding/json"
	"fmt"

	"github.com/go-resty/resty/v2"
)

var _ ImageOCR = &MistralOCR{}

// MistralOCRRequest represents the request payload for Mistral OCR API
type MistralOCRRequest struct {
	Model              string   `json:"model"`
	Document           Document `json:"document"`
	IncludeImageBase64 bool     `json:"include_image_base64"`
}

// Document represents the document structure in the request
type Document struct {
	Type     string `json:"type"`
	ImageURL string `json:"image_url"`
}

// MistralOCRResponse represents the response from Mistral OCR API
type MistralOCRResponse struct {
	Pages              []Page    `json:"pages"`
	Model              string    `json:"model"`
	DocumentAnnotation string    `json:"document_annotation"`
	UsageInfo          UsageInfo `json:"usage_info"`
}

// Page represents a page in the OCR response
type Page struct {
	Index      int        `json:"index"`
	Markdown   string     `json:"markdown"`
	Images     []Image    `json:"images"`
	Dimensions Dimensions `json:"dimensions"`
}

// Image represents an image in the OCR response
type Image struct {
	ID              string `json:"id"`
	TopLeftX        int    `json:"top_left_x"`
	TopLeftY        int    `json:"top_left_y"`
	BottomRightX    int    `json:"bottom_right_x"`
	BottomRightY    int    `json:"bottom_right_y"`
	ImageBase64     string `json:"image_base64"`
	ImageAnnotation string `json:"image_annotation"`
}

// Dimensions represents the dimensions of a page
type Dimensions struct {
	DPI    int `json:"dpi"`
	Height int `json:"height"`
	Width  int `json:"width"`
}

// UsageInfo represents usage information in the response
type UsageInfo struct {
	PagesProcessed int `json:"pages_processed"`
	DocSizeBytes   int `json:"doc_size_bytes"`
}

// MistralValidationError represents validation error response
type MistralValidationError struct {
	Detail []ValidationDetail `json:"detail"`
}

// ValidationDetail represents a validation error detail
type ValidationDetail struct {
	Loc  []string `json:"loc"`
	Msg  string   `json:"msg"`
	Type string   `json:"type"`
}

type MistralOCR struct {
	apiKey string
	client *resty.Client
}

func NewMistralOCR(apiKey string) *MistralOCR {
	return &MistralOCR{
		apiKey: apiKey,
		client: resty.New(),
	}
}

// ExtractTextFromImage calls the Mistral OCR API with the given image URL
// and returns the markdown text extracted from the image
func (m *MistralOCR) ExtractTextFromImage(requestID string, imageURL string) (string, error) {
	// Prepare the request payload
	request := MistralOCRRequest{
		Model: "mistral-ocr-latest",
		Document: Document{
			Type:     "image_url",
			ImageURL: imageURL,
		},
		IncludeImageBase64: false,
	}

	// Make the HTTP request using resty
	resp, err := m.client.R().
		SetDebug(true).
		SetHeader("Content-Type", "application/json").
		SetHeader("Authorization", "Bearer "+m.apiKey).
		SetHeader("X-Request-ID", requestID).
		SetBody(request).
		Post("https://api.mistral.ai/v1/ocr")

	if err != nil {
		return "", fmt.Errorf("failed to make request: %w", err)
	}

	// Handle different status codes
	switch resp.StatusCode() {
	case 200: // http.StatusOK
		// Parse successful response
		var ocrResponse MistralOCRResponse
		if err := json.Unmarshal(resp.Body(), &ocrResponse); err != nil {
			return "", fmt.Errorf("failed to unmarshal response: %w", err)
		}

		// Check if there's exactly one page
		if len(ocrResponse.Pages) != 1 {
			return "", fmt.Errorf("expected exactly 1 page, got %d", len(ocrResponse.Pages))
		}

		// Return the markdown content from the first (and only) page
		return ocrResponse.Pages[0].Markdown, nil

	case 442: // Validation error
		// Parse validation error response
		var validationError MistralValidationError
		if err := json.Unmarshal(resp.Body(), &validationError); err != nil {
			return "", fmt.Errorf("failed to unmarshal validation error: %w", err)
		}

		// Extract error message from the first validation detail
		if len(validationError.Detail) > 0 {
			return "", fmt.Errorf("validation error: %s", validationError.Detail[0].Msg)
		}
		return "", fmt.Errorf("validation error: unknown validation error")

	default:
		return "", fmt.Errorf("API request failed with status %d: %s", resp.StatusCode(), string(resp.Body()))
	}
}
