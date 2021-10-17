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