.PHONY: up down logs ps clean topics

# On Windows, plain `bash` resolves to the WSL launcher (System32\bash.exe); use Git Bash instead
ifeq ($(OS),Windows_NT)
BASH_EXE := "C:/Program Files/Git/bin/bash.exe"
else
BASH_EXE := bash
endif

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

topics:    ## create the 4 pipeline topics (safe to re-run)
	$(BASH_EXE) scripts/create_topics.sh
