# Linguard Docker Deployment

> **Deployment warning:** Run exactly one Linguard backend worker in one container or instance during setup and whenever WebSocket functionality is required. The setup lifecycle lock is process-local, so multiple workers or instances can race setup mutations and completion. WebSocket tickets, connections, and broadcasts are also process-local: a ticket issued by one process cannot be used by another, and broadcasts do not reach clients connected elsewhere. Multiple workers or replicas are not supported for these purposes; sticky sessions or a shared database do not make them safe. Restrict management access during setup.

## Build and Run

On a Linux host with Docker and Compose installed:

```bash
docker build -t linguard:latest .
docker compose up -d
docker compose logs -f linguard
```

Open `http://localhost:8000` and complete the setup wizard. The Compose file uses the locally built `linguard:${VERSION:-latest}` image. For a different tag, build it first and set `VERSION` consistently.

`make run` uses the same image and container paths, with Docker volumes named `linguard_data`, `linguard_backups`, and `linguard_plugins`. Compose normally prefixes these with `<project>_` instead. Do not switch launch methods without following the migration steps below. `make stop` stops without removing the container; `make clean` does not delete anything.

The container is privileged and mounts the host's `/etc/wireguard`. This grants extensive host access; run it only on a trusted Linux host, restrict access to the management port, and use HTTPS through a trusted reverse proxy configured for WebSocket upgrades on `/ws`.

The supplied configuration uses Docker's bridge network, not the host network. WireGuard interfaces, routes, forwarding and firewall rules created or inspected by Linguard are in the container's network namespace, not the Linux host's; mounting `/etc/wireguard` does not change that. Autostart only checks interfaces visible in that namespace. Existing host interfaces cannot be detected or managed through this bridge configuration, and container recreation removes container-namespace interfaces. Validate forwarding, NAT, routing, firewall rules and client connectivity on the actual deployment host before production use. Docker Desktop runs containers inside a Linux VM, so its networking, device and kernel support are not equivalent to a native Linux host; do not assume macOS host networking gives access to host WireGuard interfaces. No network mode is changed automatically.

Interface discovery is best-effort: a failed `wg` or link-state query can appear as no running interface. Check startup logs and WireGuard permissions if autostart fails; a partially created or down interface can also require manual inspection before retrying.

Compose and `make run` publish only UDP `51820:51820` by default. Each server's configured listen port must have a matching UDP container-port mapping and an accessible host port, with the advertised endpoint and upstream firewall/NAT configured accordingly. Add mappings for additional servers or change the mapping when changing a listen port, then recreate the container. `WIREGUARD_PORT` does not configure these mappings or the server. TCP `8000:8000` publishes the management UI/API.

## Configuration and Persistence

Configure the database, signing key, OIDC, and backup directory in the setup wizard or application settings. The wizard generates a signing key. The server does **not** use `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `USE_OIDC`, or `OIDC_ISSUER_URL` environment variables for these settings.

| Storage | Container path | Contents |
|---------|----------------|----------|
| `linguard_data` | `/app/data` | `linguard.config.json` database connection, default SQLite database, and backup key if configured |
| `linguard_backups` | `/app/backend/backups` | Backups when the configured directory is `./backups` |
| `linguard_plugins` | `/app/backend/plugins` | Plugin files when the configured directory is `./plugins` |
| Host bind mount | `/etc/wireguard` | WireGuard configuration files |

The image sets `LINGUARD_CONFIG_PATH=/app/data/linguard.config.json`. `LINGUARD_SQLITE_PATH=/app/data/linguard.db` overrides a relative SQLite path submitted during setup; a full SQLite URL is not remapped. If that config is missing but the default SQLite file or legacy config is present, startup fails instead of reopening setup. This cannot detect an external database or a nonstandard SQLite path if their config has been lost; preserve the config and do not run setup on an existing installation. PostgreSQL and MySQL are configured through the wizard and require a reachable database. Connection credentials in the config file and backups are sensitive: restrict access to the volumes and to any exported copies.

The image sets `LINGUARD_BACKUP_KEY_PATH=/app/data/backup.key`, inside the persisted data volume. Outside Docker, the default is `backup.key` in the parent directory of the database connection config; `LINGUARD_BACKUP_KEY_PATH` overrides it. Set an optional, strong backup encryption key during setup or as an authenticated administrator in Settings. Merely setting the path does not create a key. The key must be outside the backup directory and separate from the config and database files. Persist any overridden path and ensure it is writable by the application user. The encryption-intent marker is stored beside the key; older markers beside the config remain recognized. Directory advisory locks coordinate key changes and backup creation, so processes sharing a database must also share the same config and key directories and filesystem locking semantics.

Keep the original key in a secure external location separate from the backups; the application only reports whether it is configured. The key file is created with mode `0600`; if provisioning or restoring it yourself, use mode `0600` and ownership by the application user. Unsafe ownership or group/other access causes key reads to fail rather than silently proceeding. Before upgrading or replacing a container, preserve any existing key from its configured path. When replacing or clearing a key, retain old keys securely: existing encrypted backups are not re-encrypted and need their original key on restore. Losing a key makes backups encrypted with it unrecoverable.

Backup and plugin directories are configurable. Only `./backups` and `./plugins` (relative to `/app/backend`) are covered by the supplied mounts. For an existing installation with different configured directories, migrate their files and change the settings, or mount persistent storage at those directories. Plugin records and settings in the database do not contain the plugin source files or installed Python dependencies; preserve those separately. Fresh named volumes are populated with the image's writable directories; existing volumes or bind mounts must be writable by the `linguard` container user.

## Upgrading an Existing Container

Older images stored the database connection in `/app/backend/linguard.config.json` in the container's writable layer, so **copy it before removing or recreating the old container**. The SQLite database is normally already in the data volume. Back up the data volume and external databases first. With the old container stopped, also export plugins and backups: `/app/backend/plugins` previously had no supplied persistent mount, and older Compose versions mounted `/app/backups` instead of the actual default backup directory.

If authentication reports an insecure legacy signing key, follow [legacy signing key recovery](docs/SETUP_RECOVERY.md) before resuming service; do not delete the database or config to bypass the check.

First identify the actual mounts, rather than assuming a project name. `make run` historically used `linguard_data` and `linguard_backups`; Compose typically uses `linguard_linguard_data` and `linguard_linguard_backups`, but the project name can differ. `docker compose config` shows the *new* Compose targets, not necessarily the old container's mounts.

```bash
docker inspect linguard --format '{{range .Mounts}}{{println .Name .Source .Destination}}{{end}}'
docker compose config
docker volume ls
```

For a container named `linguard`, export the data, plugins and both possible backup locations while it is stopped. Use a new private directory outside the build context and do not overwrite previous exports:

```bash
umask 077
mkdir "$HOME/linguard-migration"
docker stop linguard
docker cp linguard:/app/data "$HOME/linguard-migration/data"
docker cp linguard:/app/backend/linguard.config.json "$HOME/linguard-migration/legacy-config.json"
# If present, each may contain distinct backups; retain both copies:
docker cp linguard:/app/backend/backups "$HOME/linguard-migration/actual-backups"
docker cp linguard:/app/backups "$HOME/linguard-migration/old-backup-volume"
docker cp linguard:/app/backend/plugins "$HOME/linguard-migration/plugins"
```

Copy commands can fail if a directory is absent; proceed only after checking the configured backup and plugin paths and saving all relevant files, including files in any custom paths. Preserve existing mounts and Python dependencies needed by plugins; installing packages into an old container's writable layer does not survive replacement. If the persistent data directory already has `linguard.config.json`, inspect both configs and select the current one. The legacy config may be missing on newer images; in that case preserve the persistent config instead. For external databases, back up the database separately. If SQLite is outside `/app/data`, export that file and any WAL files too, move them into persistent storage, and update the config URL before starting.

### Continue With Make

This retains the old Make volume names. After verifying the exports and config, remove the stopped container, build the image and create a replacement **without starting it**:

```bash
docker rm linguard
make build
docker create --name linguard --restart unless-stopped -p 8000:8000 -p 51820:51820/udp \
  -v /etc/wireguard:/etc/wireguard:rw -v linguard_data:/app/data \
  -v linguard_backups:/app/backend/backups -v linguard_plugins:/app/backend/plugins \
  --cap-add NET_ADMIN --cap-add SYS_MODULE \
  --device /dev/net/tun:/dev/net/tun --security-opt seccomp:unconfined --privileged linguard:latest
```

The database volume is reused, not copied. Inspect the destination plugin volume before copying (`docker run --rm --user root -v linguard_plugins:/plugins --entrypoint ls linguard:latest -la /plugins`). Do not overwrite existing persistent config, plugin, or backup files. If the data volume lacks the selected config, copy it in; merge exported directories only after inspecting conflicts. Preserve the old exports until recovery has been verified:

```bash
docker cp "$HOME/linguard-migration/legacy-config.json" linguard:/app/data/linguard.config.json
docker cp "$HOME/linguard-migration/actual-backups/." linguard:/app/backend/backups/
docker cp "$HOME/linguard-migration/old-backup-volume/." linguard:/app/backend/backups/
docker cp "$HOME/linguard-migration/plugins/." linguard:/app/backend/plugins/
docker run --rm --user root -v linguard_data:/app/data -v linguard_backups:/app/backend/backups -v linguard_plugins:/app/backend/plugins \
  --entrypoint chown linguard:latest -R linguard:linguard /app/data/linguard.config.json /app/backend/backups /app/backend/plugins
docker start linguard
```

Omit any copy whose source is missing, and omit the config copy if the current config is already in `/app/data`. Resolve duplicate filenames manually before copying; `docker cp` overwrites matching files. The explicit `docker create` matches `make run`, which can be used for subsequent new containers after backing up any writable-layer data.

### Continue With Compose

If the old container was already Compose-managed under the same project and `docker compose config` shows the same data and backup volume names identified above, follow the Make procedure conceptually but use `docker compose create` and `docker compose run --rm --no-deps --user root --entrypoint chown linguard ...` in place of `docker create` and the helper `docker run`. Inspect the Compose plugin destination too; its project-prefixed name differs from Make's. Export first: Compose may remove the old container during creation.

For a Make-to-Compose switch, the volumes are normally different. Do not silently use empty Compose volumes or overwrite an existing deployment. If the names displayed by `docker compose config` match the old Make volume names, use the same-volume procedure above instead. With the old container stopped and all exports verified:

```bash
docker rm linguard
docker build -t linguard:latest .
docker compose create
# Inspect destination contents BEFORE copying. If any is nonempty, stop and
# reconcile it manually rather than overwriting another installation.
docker compose run --rm --no-deps --user root --entrypoint sh linguard -c 'ls -la /app/data /app/backend/backups /app/backend/plugins'
# Only if all destinations are empty:
docker cp "$HOME/linguard-migration/data/." linguard:/app/data/
docker cp "$HOME/linguard-migration/legacy-config.json" linguard:/app/data/linguard.config.json
docker cp "$HOME/linguard-migration/actual-backups/." linguard:/app/backend/backups/
docker cp "$HOME/linguard-migration/old-backup-volume/." linguard:/app/backend/backups/
docker cp "$HOME/linguard-migration/plugins/." linguard:/app/backend/plugins/
docker compose run --rm --no-deps --user root --entrypoint chown linguard -R linguard:linguard /app/data /app/backend/backups /app/backend/plugins
docker compose start
```

Omit missing sources and resolve filename conflicts manually. If the data export already contains the current config, omit the legacy-config copy. The old Make volumes remain untouched. After starting, verify the expected database, users, settings, backups and loaded plugins before securely removing exports. Never run setup against an apparently empty replacement until the cause is understood; a stopped container can be copied, a deleted one cannot.

## CI and Releases

CI runs the backend suite, frontend build, setup-storage Node tests, and mocked Chromium regression specs. The mocked tests are maintained alongside ongoing frontend changes and must be committed with the workflow. Successful CI on `dev` publishes the `dev` image; successful CI on `main` publishes `stable` and `latest`. When `version.json` contains a new `major.minor.patch` version, the stable workflow also publishes that immutable version tag and creates a GitHub release. An existing version tag pointing at another commit is not moved; bump `version.json` for the next release. Publishing requires GitHub Actions package and contents permissions, and the workflows must exist on the repository's default branch for `workflow_run` triggers.

## Backups and Recovery

With a global backup key configured, newly created manual, setup and scheduled backups are encrypted using AES-256-GCM. Without a global key, backups are plaintext unless an API request explicitly supplies a passphrase and requests encryption; a request for encryption without a key or passphrase fails. An unreadable or unsafe key file fails rather than falling back to plaintext. Once encryption intent is recorded in the database, a missing key or marker blocks backups until the key is recovered or encryption is explicitly cleared by an administrator. Preserve both the database and key directory when migrating.

At the first upgrade, historical encrypted-backup records alone do not prove a global key was configured: they may represent legacy base64 or one-off encryption. If the original key, marker, and database intent were already lost before migration, the old global policy cannot be reconstructed and the installation may start without a global key. Verify key status and restore the original key before creating backups. Explicit clearing can result in plaintext backups.

Existing plaintext backups and plaintext imports remain plaintext after a key is set; imports are stored as supplied. Older backups may be unencrypted even if encryption was requested, and the legacy restore path for records marked encrypted may only base64-decode them; base64 is not encryption. Backups can contain WireGuard private and preshared keys and integration configuration. Restrict access and use external encryption for plaintext backups, database dumps and exports, in storage and transit. Encryption does not protect against a server compromise that exposes the key or plaintext data.

For a consistent SQLite filesystem copy, stop the container first and copy the entire data directory, including any SQLite WAL files and the connection config. For external databases, use the database vendor's backup procedure. Store exports securely and test restoration.

```bash
umask 077
docker compose stop
docker cp linguard:/app/data ./linguard-data-backup
docker cp linguard:/app/backend/backups ./linguard-backups-backup
docker cp linguard:/app/backend/plugins ./linguard-plugins-backup
docker compose start
```

Do not use `docker compose down -v` unless you intend to delete the named volumes. Before changing mounts or upgrading, back up the database/config, backup files, and plugin files.

## Troubleshooting

- Check `docker compose logs linguard` for startup and database errors.
- Check the configured backup path and volume permissions if backups fail.
- The runtime user needs appropriate access to `/etc/wireguard`; do not make that directory world-writable. Configure ownership or narrowly scoped permissions for your host.
- Linux WireGuard support, network namespaces, firewall rules, and elevated privileges must be validated on the deployment host.
