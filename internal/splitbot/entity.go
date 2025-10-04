package splitbot

type Message struct {
	Text      string
	ImagePath string
	From      User
}

type User struct {
	ID       int64
	Username string
}
