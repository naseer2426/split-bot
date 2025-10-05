package splitbot

type Bot struct {
}

func NewBot() *Bot {
	return &Bot{}
}

func (b *Bot) HandleMessage(requestID string, message *Message) (string, error) {
	if message.Image != nil {
		return message.Image.ExtractedText, nil
	}
	// If no image path, return the text message
	return message.Text, nil
}
