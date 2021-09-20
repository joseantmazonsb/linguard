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

ETC_DIR="/etc/linguard"
VAR_DIR="/var/www/linguard"
LOG_DIR="/var/log/linguard"

info "Creating '$ETC_DIR'..."

if [[ -d "$ETC_DIR" ]]; then
    while true; do
    warn -n "'$ETC_DIR' already exists. Shall I overwrite it? [y/n] "
      read yn
      case $yn in
          [Yy]* ) rm -rf "$ETC_DIR"; break;;
          [Nn]* ) info "Aborting..."; exit;;
          * ) echo "Please answer yes or no.";;
      esac
    done
fi
CONFIG_DIR="$ETC_DIR/config"
mkdir -p "$CONFIG_DIR"
cp config/linguard.sample.yaml "$CONFIG_DIR/linguard.yaml"
cp config/uwsgi.sample.yaml "$CONFIG_DIR/uwsgi.yaml"

info "Creating '$VAR_DIR'..."

if [[ -d "$VAR_DIR" ]]; then
    while true; do
    warn -n "'$VAR_DIR' already exists. Shall I overwrite it? [y/n] "
      read yn
      case $yn in
          [Yy]* ) rm -rf "$VAR_DIR"; break;;
          [Nn]* ) info "Aborting..."; exit;;
          * ) echo "Please answer yes or no.";;
      esac
    done
fi
mkdir -p "$VAR_DIR"
cp -r linguard "$VAR_DIR"
cp requirements.txt "$VAR_DIR"

info "Creating '$LOG_DIR'..."

if [[ -d "$LOG_DIR" ]]; then
    while true; do
    warn -n "'$LOG_DIR' already exists. Shall I overwrite it? [y/n] "
      read yn
      case $yn in
          [Yy]* ) rm -rf "$LOG_DIR"; mkdir -p "$LOG_DIR"; break;;
          [Nn]* ) break;;
          * ) echo "Please answer yes or no.";;
      esac
    done
fi


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
python3 -m venv "$VAR_DIR/venv"
source "$VAR_DIR/venv/bin/activate"
if [ $? -ne 0 ]; then
    fatal "Unable to activate virtual environment."
    exit 1
fi
debug "Upgrading pip..."
python3 -m pip install --upgrade pip
debug "Installing python requirements..."
python3 -m pip install -r "$VAR_DIR/requirements.txt"
if [ $? -ne 0 ]; then
    fatal "Unable to install requirements."
    exit 1
fi
deactivate

info "Settings permissions..."
groupadd linguard
useradd -g linguard linguard
chown -R linguard:linguard "$VAR_DIR"
chown -R linguard:linguard "$ETC_DIR"
chown -R linguard:linguard "$LOG_DIR"
chmod +x -R "$VAR_DIR/linguard/core/tools"
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg" > /etc/sudoers.d/linguard
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick" >> /etc/sudoers.d/linguard

info "Adding linguard service..."
cp systemd/linguard.service /etc/systemd/system/
chmod 644 /etc/systemd/system/linguard.service

info "All set! Run 'systemctl start linguard.service' to get started."