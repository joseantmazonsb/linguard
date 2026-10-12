#!/bin/bash
set -e

VERSION="${VERSION:-latest}"
IMAGE="linguard:${VERSION}"

echo "Building Linguard Docker image..."
docker build --tag "$IMAGE" .

echo "✅ Build complete: $IMAGE"
