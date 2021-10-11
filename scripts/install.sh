#!/bin/bash

source ./log.sh

if [[ $EUID -ne 0 ]]; then
   fatal "This script must be run as superuser! Try using sudo."
   exit 1
fi

if [[ $# -gt 0 ]]; then
  fatal "Invalid arguments."
  info "Usage: $0"
  exit 1
fi

INSTALL_DIR="/var/www/linguard"

info "Creating '$INSTALL_DIR'..."

if [[ -d "$INSTALL_DIR" ]]; then
    while true; do
    warn -n "'$INSTALL_DIR' already exists. Shall I overwrite it? [y/n] "
      read yn
      case $yn in
          [Yy]* ) rm -rf "$INSTALL_DIR"; break;;
          [Nn]* )
            info "Aborting...";
            rm -rf "$ETC_DIR"
            exit;;
          * ) echo "Please answer yes or no.";;
      esac
    done
fi
mkdir -p "$INSTALL_DIR"
cp -a linguard "$INSTALL_DIR"
SOURCE_DIR="$INSTALL_DIR/linguard"
DATA_DIR="$INSTALL_DIR/data"
mkdir -p "$DATA_DIR"

cp config/uwsgi.sample.yaml "$DATA_DIR/uwsgi.yaml"

cp requirements.txt "$INSTALL_DIR"

info "Installing dependencies..."
debug "Updating packages list..."
apt-get -qq update
dependencies="python3 python3-venv wireguard iptables libpcre3 libpcre3-dev uwsgi uwsgi-plugin-python3"
debug "The following packages will be installed: $dependencies"
apt-get -qq install $dependencies
if [ $? -ne 0 ]; then
    fatal "Unable to install dependencies."
    exit 1
fi

info "Setting up virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"
if [ $? -ne 0 ]; then
    fatal "Unable to activate virtual environment."
    exit 1
fi
debug "Upgrading pip..."
python3 -m pip install --upgrade pip
debug "Installing python requirements..."
python3 -m pip install -r "$INSTALL_DIR/requirements.txt"
if [ $? -ne 0 ]; then
    fatal "Unable to install requirements."
    exit 1
fi
deactivate

info "Settings permissions..."
groupadd linguard
useradd -g linguard linguard
chown -R linguard:linguard "$INSTALL_DIR"
chmod +x -R "$SOURCE_DIR/core/tools"
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg" > /etc/sudoers.d/linguard
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick" >> /etc/sudoers.d/linguard

info "Adding linguard service..."
cp systemd/linguard.service /etc/systemd/system/
chmod 644 /etc/systemd/system/linguard.service

info "All set! Run 'systemctl start linguard.service' to get started."