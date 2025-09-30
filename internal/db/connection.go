package db

import (
	"fmt"
	"os"
	"sync"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

var DB *gorm.DB
var once sync.Once

// Init establishes a GORM connection to Postgres using the DATABASE_URL environment variable.
func Init() error {
	if DB != nil {
		return nil
	}

	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		return fmt.Errorf("DATABASE_URL is not set")
	}

	database, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return err
	}

	DB = database
	return nil
}

func GetDB() *gorm.DB {
	once.Do(func() {
		err := Init()
		if err != nil {
			panic(err)
		}
	})
	return DB
}
