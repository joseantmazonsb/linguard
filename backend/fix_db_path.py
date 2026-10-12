#!/usr/bin/env python3
"""Ensure the container config points at the persistent volume for SQLite.

Creates /app/backend/linguard.config.json if it is not baked into the image
(it is excluded via .dockerignore) and always normalizes the SQLite URL to
/app/data/linguard.db so data survives container recreation.
"""
import json
import os

CONFIG_PATH = '/app/backend/linguard.config.json'
VOLUME_DB_URL = 'sqlite+aiosqlite:////app/data/linguard.db'

os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)

config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'r') as f:
        try:
            config = json.load(f)
        except Exception:
            config = {}

config['database'] = {'type': 'sqlite', 'url': VOLUME_DB_URL}

with open(CONFIG_PATH, 'w') as f:
    json.dump(config, f, indent=2)

print(f'Database path set to {VOLUME_DB_URL}')