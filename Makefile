.PHONY: build run stop restart clean logs shell help

VERSION ?= latest
IMAGE = linguard:$(VERSION)

help:
	@echo "Linguard Docker Commands"
	@echo ""
	@echo "  make build              Build Docker image"
	@echo "  make run                Run Linguard container"
	@echo "  make stop               Stop Linguard container"
	@echo "  make restart            Restart Linguard container"
	@echo "  make clean              Remove stopped container (volumes retained)"
	@echo "  make logs               View container logs"
	@echo "  make shell              Open shell in container"

build:
	@VERSION="$(VERSION)" ./scripts/build.sh

run:
	@docker run -d \
		--name linguard \
		--restart unless-stopped \
		-p 8000:8000 \
		-p 51820:51820/udp \
		-v /etc/wireguard:/etc/wireguard:rw \
		-v linguard_data:/app/data \
		-v linguard_backups:/app/backend/backups \
		-v linguard_plugins:/app/backend/plugins \
		--cap-add NET_ADMIN \
		--cap-add SYS_MODULE \
		--device /dev/net/tun:/dev/net/tun \
		--security-opt seccomp:unconfined \
		--privileged \
		${IMAGE}

stop:
	@docker stop linguard

restart:
	@docker restart linguard

clean:
	@echo "Warning: removing the container deletes any config, backups or plugins in its writable layer. See docker-readme.md first."
	@echo "Remove the stopped container manually after backing it up; volumes are retained."

logs:
	@docker logs --tail 50 linguard

shell:
	@docker exec -it linguard /bin/bash
