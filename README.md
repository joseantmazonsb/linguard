# Linguard

[![GitHub](https://img.shields.io/github/license/joseantmazonsb/linguard)](LICENSE.md) ![Python version](https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9-blue) [![build](https://github.com/joseantmazonsb/linguard/actions/workflows/main.yaml/badge.svg)](https://github.com/joseantmazonsb/linguard/actions/workflows/main.yaml) [![codecov](https://codecov.io/gh/joseantmazonsb/linguard/branch/main/graph/badge.svg)](https://codecov.io/gh/joseantmazonsb/linguard)

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/joseantmazonsb/linguard)](https://github.com/joseantmazonsb/linguard/releases) [![GitHub all releases](https://img.shields.io/github/downloads/joseantmazonsb/linguard/total)](https://github.com/joseantmazonsb/linguard/releases) [![Docker Pulls](https://img.shields.io/docker/pulls/joseantmazonsb/linguard)](https://hub.docker.com/repository/docker/joseantmazonsb/linguard)


Linguard aims to provide an easy way to manage your WireGuard server, and it's written in Python3 and powered by Flask.

Check out [the wiki](https://github.com/joseantmazonsb/linguard/wiki) for additional info!

## Table of contents
- [Screenshots](#screenshots)
- [Installation](#installation)
    - [Git](#git)
    - [Debian package](#debian-package)
    - [Docker](#docker)
- [Contributing](#contributing)

## Screenshots

![Signup](images/signup.png)
![Login](images/login.png)
![Network interfaces](images/network-section-1.png)
![Routing information](images/network-section-2.png)
![Wireguard interfaces section (1)](images/wireguard-section-1.png)
![Wireguard interfaces section (2)](images/wireguard-section-2.png)
![Edit wireguard interface configuration (1)](images/wireguard-edit-1.png)
![Edit wireguard interface configuration (2)](images/wireguard-edit-2.png)
![Edit wireguard peer configuration](images/peer-edit-1.png)
![Settings](images/settings.png)

## Installation

### Git

1. Download the installation script and run it. You must supply the installation directory (for instance, `/var/www/linguard`) and (optionally) the tag to check out.
    ```bash
    wget -q https://raw.githubusercontent.com/joseantmazonsb/linguard/main/scripts/install.sh .
    chmod +x install.sh
    sudo ./install.sh <install_folder> [git_branch]
    ```
2. Edit the configuration files located in `/var/www/linguard/config` to fit your needs.
3. Start linguard:
    ```bash
    sudo -u linguard /var/www/linguard/scripts/run.sh
    ```
    or, if you renamed the uwsgi configuration file: 
    ```bash
    sudo -u linguard uwsgi --yaml /path/to/uwsgi/config/file
    ```

### Debian package

### Docker

## Contributing

You may contribute by opening new issues, commenting on existent ones and creating pull requests with new features and bugfixes. Any help is welcome :)
