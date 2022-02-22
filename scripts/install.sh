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
cp -a linguard/web "$INSTALL_DIR"
cp -a linguard/cli "$INSTALL_DIR"
DATA_DIR="$INSTALL_DIR/data"
mkdir -p "$DATA_DIR"

info "Installing dependencies..."
debug "Updating packages list..."
apt-get -qq update
dependencies="sudo wireguard iptables"
debug "The following packages will be installed: $dependencies"
apt-get -qq install $dependencies
if [ $? -ne 0 ]; then
    fatal "Unable to install dependencies."
    exit 1
fi

info "Settings permissions..."
groupadd linguard
useradd -g linguard linguard
chown -R linguard:linguard "$INSTALL_DIR"
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg" > /etc/sudoers.d/linguard
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick" >> /etc/sudoers.d/linguard

info "Adding linguard service..."
cp systemd/linguard.service /etc/systemd/system/
chmod 644 /etc/systemd/system/linguard.service

info "All set! Run 'systemctl start linguard.service' to get started."