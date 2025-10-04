package main

import (
	"fmt"
	"log"
	"os"

	"github.com/gin-contrib/cors"
	"github.com/gin-contrib/requestid"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/naseer2426/split-bot/internal/api"
	"github.com/naseer2426/split-bot/internal/splitbot"
	"github.com/naseer2426/split-bot/internal/telegram"
)

func main() {
	err := initEnv()
	if err != nil {
		panic(err)
	}
	router := initRouter()
	t := initTelegramWebhook()
	// run migrations
	// db.AutoMigrate()

	router.GET("/", api.HealthCheck)
	router.POST("/telegram/webhook", t.TelegramWebhook)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	if err := router.Run(fmt.Sprintf(":%s", port)); err != nil {
		log.Fatalf("failed to start server: %v", err)
	}
}

func initEnv() error {
	// Load environment variables from .env file if present
	if err := godotenv.Load(); err != nil {
		// Only log if the file is missing; envs may be provided by the environment
		if !os.IsNotExist(err) {
			log.Printf("warning: could not load .env: %v", err)
			return err
		}
	}
	return nil
}

func initRouter() *gin.Engine {
	router := gin.Default()

	router.Use(requestid.New())
	// Allow CORS for all origins
	router.Use(cors.New(cors.Config{
		AllowAllOrigins: true,
		AllowMethods:    []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowHeaders:    []string{"Origin", "Content-Length", "Content-Type", "Authorization", "Accept", "X-Requested-With"},
		ExposeHeaders:   []string{"Content-Length"},
	}))

	return router
}

func initTelegramWebhook() *api.TelegramWebhook {
	return &api.TelegramWebhook{
		TelegramAPI: telegram.NewTelegramAPI(os.Getenv("TELEGRAM_BOT_TOKEN")),
		SplitBot:    splitbot.NewBot(),
	}
}
