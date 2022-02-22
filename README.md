# Linguard

[![GitHub](https://img.shields.io/github/license/joseantmazonsb/linguard)](LICENSE.md) ![Dotnet version](https://img.shields.io/badge/6-blue?logo=dotnet&logoColor=white) [![Stable workflow status](https://github.com/joseantmazonsb/linguard/actions/workflows/stable-test.yaml/badge.svg)](https://github.com/joseantmazonsb/linguard/actions/workflows/stable-test.yaml) [![Latest workflow status](https://github.com/joseantmazonsb/linguard/actions/workflows/latest-test.yaml/badge.svg)](https://github.com/joseantmazonsb/linguard/actions/workflows/latest-test.yaml) [![Stable Documentation Status](https://readthedocs.org/projects/linguard/badge/?version=stable)](https://linguard.readthedocs.io/en/stable/?badge=stable) [![codecov](https://codecov.io/gh/joseantmazonsb/linguard/branch/dev/graph/badge.svg)](https://codecov.io/gh/joseantmazonsb/linguard)

[![GitHub release (latest SemVer including pre-releases)](https://img.shields.io/github/v/release/joseantmazonsb/linguard?color=green&include_prereleases&logo=github)](https://github.com/joseantmazonsb/linguard/releases) [![GitHub all releases](https://img.shields.io/github/downloads/joseantmazonsb/linguard/total?logo=github)](https://github.com/joseantmazonsb/linguard/releases)


Linguard aims to provide a clean, simple yet powerful web GUI to manage your WireGuard server.

**[Read the docs](https://linguard.readthedocs.io) for further information!**

## Key features

* Management of Wireguard interfaces and peers via web. Interfaces can be created, removed, edited, exported and brought up and down directly from the web GUI. Peers can be created, removed, edited and downloaded at anytime as well.
* IPv6 support.
* Display stored and real time traffic data using charts (storage of traffic data may be manually disabled).
* Display general network information.
* Encrypted user credentials.
* Easy management through the ``linguard`` systemd service.
* CLI tool.

## Installation

### As a `systemd` service

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

1. Download the [`docker-compose.yaml` file](https://raw.githubusercontent.com/joseantmazonsb/linguard/main/docker/docker-compose.yaml).
2. Run Linguard: 
   ```bash
   sudo docker-compose up -d
   ```
NOTE: You can check all available tags [here](https://github.com/joseantmazonsb/linguard/pkgs/container/linguard/versions).