#!/bin/bash

bold=$(tput bold)
default=$(tput sgr0)
cyan=$(tput setaf 6)
red=$(tput setaf 1)
yellow=$(tput setaf 3)
dark_gray=$(tput setaf 8)

function log() {
  level=$1
  if [ $# -gt 2 ]; then
    options=$2
    msg=$3
  else
    options=""
    msg=$2
  fi
  case $level in
        DEBUG* ) echo -e $options "${dark_gray}${bold}[DEBUG]${default} ${dark_gray}$msg${default}";;
        INFO* ) echo -e $options "${cyan}${bold}[INFO]${default} ${cyan}$msg${default}";;
        WARN* ) echo -e $options "${yellow}${bold}[WARN]${default} ${yellow}$msg${default}";;
        ERROR* ) echo -e $options "${red}${bold}[ERROR]${default} ${red}$msg${default}";;
        FATAL* ) echo -e $options "${red}${bold}[FATAL] $msg${default}";;
        * ) echo "Invalid log level: '$level'";;
    esac
}

function debug() {
  log DEBUG "$@"
}

function info() {
  log INFO "$@"
}

function warn() {
  log WARN "$@"
}

function err() {
  log ERROR "$@"
}

function fatal() {
  log FATAL "$@"
}


if [[ $EUID -ne 0 ]]; then
   fatal "This script must be run as superuser! Try using sudo."
   exit 1
fi

info "Installing dependencies..."
debug "Updating packages list..."
apt-get -qq update
dependencies="git python3 python3-pip python3-virtualenv wireguard iptables libpcre3 libpcre3-dev uwsgi uwsgi-plugin-python3"
debug "The following packages will be installed: $dependencies"
apt-get -qq install $dependencies

INSTALLATION_PATH=/var/www/linguard
clone=true
info "Cloning repository in $INSTALLATION_PATH..."
if [[ -d "$INSTALLATION_PATH" ]]; then
  while true; do
  warn -n "$INSTALLATION_PATH already exists. Shall I overwrite it? [y/n] "
    read yn
    case $yn in
        [Yy]* ) rm -rf $INSTALLATION_PATH; break;;
        [Nn]* ) clone=false; break;;
        * ) echo "Please answer yes or no.";;
    esac
  done
fi

if [ "$clone" = true ]; then
  git clone https://github.com/joseantmazonsb/linguard.git $INSTALLATION_PATH
fi
info "Setting up virtual environment..."
virtualenv ${INSTALLATION_PATH}/venv
source ${INSTALLATION_PATH}/venv/bin/activate
debug "Installing python requirements..."
pip3 install -r ${INSTALLATION_PATH}/requirements.txt
deactivate

info "Settings permissions..."
groupadd linguard
useradd -g linguard linguard
chown -R linguard:linguard $INSTALLATION_PATH
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg" > /etc/sudoers.d/linguard
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick" >> /etc/sudoers.d/linguard

info "DONE!"