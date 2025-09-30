package main

import (
	"fmt"
	"log"
	"os"

	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
	"github.com/naseer2426/go-backend-template/internal/api"
)

func main() {
	err := initEnv()
	if err != nil {
		panic(err)
	}
	router := initRouter()
	// run migrations
	// db.AutoMigrate()

	router.GET("/", api.HealthCheck)

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
	// Allow CORS for all origins
	router.Use(cors.New(cors.Config{
		AllowAllOrigins: true,
		AllowMethods:    []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowHeaders:    []string{"Origin", "Content-Length", "Content-Type", "Authorization", "Accept", "X-Requested-With"},
		ExposeHeaders:   []string{"Content-Length"},
	}))

	return router
}
