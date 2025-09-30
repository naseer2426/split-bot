package db

import "log"

// AutoMigrate runs GORM auto-migrations for all models.
func AutoMigrate() {
	database := GetDB()
	// pass all the models which you want to sync here
	if err := database.AutoMigrate(nil); err != nil {
		log.Fatalf("failed to run migrations: %v", err)
	}
}
