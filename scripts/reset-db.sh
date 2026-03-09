#!/bin/bash
# Reset database for E2E tests

echo "Resetting database..."
docker exec wireguard-postgres-dev psql -U wireguard -d wireguard -c "TRUNCATE users, servers, peers, global_settings, backups, audit_logs, events, integrations, traffic_alerts RESTART IDENTITY CASCADE;"

echo "Verifying users table is empty..."
USER_COUNT=$(docker exec wireguard-postgres-dev psql -U wireguard -d wireguard -t -c "SELECT COUNT(*) FROM users;")

if [ "$USER_COUNT" -eq 0 ]; then
  echo "✓ Database reset successful"
  exit 0
else
  echo "✗ Database reset failed - $USER_COUNT users still exist"
  exit 1
fi
