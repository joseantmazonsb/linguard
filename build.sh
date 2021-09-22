#!/bin/bash

source ./scripts/log.sh

if [[ $# -gt 0 ]]; then
  fatal "Invalid arguments."
  info "Usage: $0"
  exit 1
fi

OUT_DIR=$(pwd)
DIST_DIR="$OUT_DIR/dist"

info "Creating dist folder in '$DIST_DIR'..."

if [[ -d "$DIST_DIR" ]]; then
    while true; do
    warn -n "'$DIST_DIR' already exists. Shall I overwrite it? [y/n] "
      read yn
      case $yn in
          [Yy]* )
            rm -rf "$DIST_DIR";
            if [ $? -ne 0 ]; then
              fatal "Unable to overwrite '$DIST_DIR'."
              exit 1
            fi
            break;;
          [Nn]* )
            info "Aborting...";
            exit;;
          * ) echo "Please answer yes or no.";;
      esac
    done
    if [ $? -ne 0 ]; then
      fatal "Unable to overwrite '$DIST_DIR'."
      exit 1
    fi
fi
mkdir -p "$DIST_DIR"

info "Copying source code..."
CODE_DIR="$DIST_DIR/linguard"
mkdir "$CODE_DIR"
cp -r linguard/common "$CODE_DIR/common"
cp -r linguard/core "$CODE_DIR/core"
cp -r linguard/web "$CODE_DIR/web"
cp linguard/__main__.py "$CODE_DIR"
cp linguard/__init__.py "$CODE_DIR"

info "Copying configuration files..."
cp -r systemd/ "$DIST_DIR"
CONFIG_DIR="$DIST_DIR/config"
mkdir "$CONFIG_DIR"
find config -type f | grep -E "[^.]+\.sample\.yaml" | xargs -i cp {} "$CONFIG_DIR"

info "Exporting python requirements..."
poetry export --without-hashes -f requirements.txt -o requirements.txt
if [ $? -ne 0 ]; then
  fatal "Unable to export requirements."
  exit 1
fi
mv requirements.txt "$DIST_DIR"

info "Copying scripts..."
cp scripts/install.sh "$DIST_DIR"
cp scripts/log.sh "$DIST_DIR"

version=$(poetry version -s)
zip_name="linguard-$version.tar.gz"

info "Compressing package into '$zip_name'..."
cd "$DIST_DIR"
tar -czf "$zip_name" *
mv "$zip_name" ..
cd - > /dev/null
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"
mv "$zip_name" "$DIST_DIR"
info "Done!"