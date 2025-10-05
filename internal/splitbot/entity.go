package splitbot

type Message struct {
	Text  string
	Image *Image
	From  User
}

type Image struct {
	Url           string
	FileID        string
	ExtractedText string
}

type User struct {
	ID       int64
	Username string
}
