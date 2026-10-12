.PHONY: build run stop clean help

VERSION ?= latest
IMAGE = linguard

help:
	@echo "Linguard Docker Commands"
	@echo ""
	@echo "  make build              Build Docker image"
	@echo "  make run                Run Linguard container"
	@echo "  make stop               Stop Linguard container"
	@echo "  make restart            Restart Linguard container"
	@echo "  make clean              Remove container and volumes"
	@echo "  make logs               View container logs"
	@echo "  make shell              Open shell in container"

build:
	@./scripts/build.sh

run:
	@docker run -d \
		--name linguard \
		--restart unless-stopped \
		-p 8000:8000 \
		-v /etc/wireguard:/etc/wireguard:rw \
		-v linguard_data:/app/data \
		-v linguard_backups:/app/backups \
		-e DATABASE_URL=sqlite+aiosqlite:////app/data/linguard.db \
		-e SECRET_KEY=$(shell openssl rand -hex 32) \
		--cap-add NET_ADMIN \
		--device /dev/net/tun:/dev/net/tun \
		--security-opt seccomp:unconfined \
		--privileged \
		${IMAGE}

stop:
	@docker stop linguard || true
	@docker rm linguard || true

restart:
	@docker restart linguard

clean:
	@docker stop linguard || true
	@docker rm linguard || true
	@docker volume rm linguard_data || true
	@docker volume rm linguard_backups || true

logs:
	@docker logs --tail 50 linguard

shell:
	@docker exec -it linguard /bin/bash
