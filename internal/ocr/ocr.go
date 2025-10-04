package ocr

type ImageOCR interface {
	ExtractTextFromImage(requestID string, imageURL string) (string, error)
}
