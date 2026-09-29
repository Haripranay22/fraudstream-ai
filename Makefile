.PHONY: up down logs ps clean

up:        ## start Kafka + Kafka UI (http://localhost:8080)
	docker compose up -d --wait

down:      ## stop containers, keep data
	docker compose down

logs:      ## follow Kafka logs
	docker compose logs -f kafka

ps:        ## container status
	docker compose ps

clean:     ## stop and DELETE all Kafka data
	docker compose down -v
