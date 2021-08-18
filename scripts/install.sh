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

if [[ $# -gt 2 ]] || [[ $# -lt 1 ]]; then
  fatal "Invalid arguments."
  info "Usage: $0 <install_folder> [git_branch]\n\t <install_folder>\t| Path where Linguard will be checked out and installed.\n\t [git_branch]\t\t| Tag to download. Default: main."
  exit 2
fi

INSTALLATION_PATH=$1
GIT_TAG=$2
if [[ $GIT_TAG == "" ]]; then
  GIT_TAG="main"
fi
debug "Installation path set to '$INSTALLATION_PATH'."
debug "Git tag set to '$GIT_TAG'."

info "Installing dependencies..."
debug "Updating packages list..."
apt-get -qq update
dependencies="git python3 python3-pip python3-virtualenv wireguard iptables libpcre3 libpcre3-dev uwsgi uwsgi-plugin-python3"
debug "The following packages will be installed: $dependencies"
apt-get -qq install $dependencies

info "Cloning repository in $INSTALLATION_PATH..."
clone=true
if [[ -d "$INSTALLATION_PATH" ]]; then
  while true; do
  warn -n "$INSTALLATION_PATH already exists. Shall I overwrite it? [y/n] "
    read yn
    case $yn in
        [Yy]* ) rm -rf "$INSTALLATION_PATH"; break;;
        [Nn]* ) clone=false; break;;
        * ) echo "Please answer yes or no.";;
    esac
  done
fi

if [ "$clone" = true ]; then
  git clone --branch "$GIT_TAG" https://github.com/joseantmazonsb/linguard.git "$INSTALLATION_PATH"
fi

info "Setting up virtual environment..."
rm -rf "${INSTALLATION_PATH}"/venv
virtualenv "${INSTALLATION_PATH}"/venv
source "${INSTALLATION_PATH}"/venv/bin/activate
debug "Installing python requirements..."
pip3 install -r "${INSTALLATION_PATH}"/requirements.txts
deactivate

info "Settings permissions..."
groupadd linguard
useradd -g linguard linguard
chown -R linguard:linguard "$INSTALLATION_PATH"
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg" > /etc/sudoers.d/linguard
echo "linguard ALL=(ALL) NOPASSWD: /usr/bin/wg-quick" >> /etc/sudoers.d/linguard
chmod +x "${INSTALLATION_PATH}"/scripts/run.sh

info "DONE!"