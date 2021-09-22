# Linguard

[![GitHub](https://img.shields.io/github/license/joseantmazonsb/linguard)](LICENSE.md) ![Python version](https://img.shields.io/badge/python-3.7%20%7C%203.8%20%7C%203.9-blue?logo=python&logoColor=yellow) [![build](https://github.com/joseantmazonsb/linguard/actions/workflows/main.yaml/badge.svg)](https://github.com/joseantmazonsb/linguard/actions/workflows/main.yaml) [![codecov](https://codecov.io/gh/joseantmazonsb/linguard/branch/main/graph/badge.svg)](https://codecov.io/gh/joseantmazonsb/linguard)

[![GitHub release (latest SemVer including pre-releases)](https://img.shields.io/github/v/release/joseantmazonsb/linguard?color=green&include_prereleases&logo=github)](https://github.com/joseantmazonsb/linguard/releases) [![GitHub all releases](https://img.shields.io/github/downloads/joseantmazonsb/linguard/total?logo=github)](https://github.com/joseantmazonsb/linguard/releases) [![Docker Pulls](https://img.shields.io/docker/pulls/joseantmazonsb/linguard)](https://hub.docker.com/repository/docker/joseantmazonsb/linguard)


Linguard aims to provide an easy way to manage your WireGuard server, and it's written in Python3 and powered by Flask.

Check out [the wiki](https://github.com/joseantmazonsb/linguard/wiki) for additional info!

## Table of contents
- [Installation](#installation)
    - [Release](#release)
    - [Docker](#docker)
- [Screenshots](#screenshots)
- [Contributing](#contributing)

## Installation

### Release

1. Download [any release](https://github.com/joseantmazonsb/linguard/releases).
    
2. Extract it and run the installation script:
    ```bash
    chmod +x install.sh
    sudo ./install.sh
    ```
3. Run Linguard: 
    ```bash
    sudo systemctl start linguard.service
    ```

### Docker

## Screenshots

![Dashboard (1)](images/dashboard-1.png)
![Dashboard (2)](images/dashboard-2.png)
![Network interfaces](images/network-section-1.png)
![Routing information](images/network-section-2.png)
![Wireguard interfaces section (1)](images/wireguard-section-1.png)
![Wireguard interfaces section (2)](images/wireguard-section-2.png)
![Edit wireguard interface configuration (1)](images/wireguard-edit-1.png)
![Edit wireguard interface configuration (2)](images/wireguard-edit-2.png)
![Edit wireguard interface configuration (3)](images/wireguard-edit-3.png)
![Edit wireguard peer configuration (1)](images/peer-edit-1.png)
![Edit wireguard peer configuration (2)](images/peer-edit-2.png)
![Settings (1)](images/settings-1.png)
![Settings (2)](images/settings-2.png)

## Contributing

You may contribute by opening new issues, commenting on existent ones and creating pull requests with new features and bugfixes. Any help is welcome :)
