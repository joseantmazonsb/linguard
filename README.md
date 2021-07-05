# Linguard

Linguard aims to provide an easy way to manage your WireGuard server, and it's written in Python3 and powered by Flask.

## Table of contents
- [Screenshots](#screenshots)
- [Installation](#installation)
    - [Git](#git)
    - [Debian package](#debian-package)
    - [Docker](#docker)
- [Docs](#docs)
    - [Configuration](#configuration)
    - [Classes](#classes)
- [Notes](#notes)
    - [Changelog](#changelog)
    - [Known issues](#known-issues)
- [Contributing](#contributing)

## Screenshots

![Network interfaces](images/network-section-1.png)
![Routing information](images/network-section-2.png)
![Wireguard interfaces section (1)](images/wireguard-section-1.png)
![Wireguard interfaces section (2)](images/wireguard-section-2.png)
![Edit wireguard interface configuration (1)](images/wireguard-edit-1.png)
![Edit wireguard interface configuration (2)](images/wireguard-edit-2.png)
![Edit wireguard peer configuration](images/peer-edit-1.png)

## Installation

### Git

1. Install dependencies:
    ```bash
    sudo apt update
    sudo apt install wireguard iptables uwsgi uwsgi-plugin-python3 libpcre3 libpcre3-dev
    ```
2. Download any release and put the files somewhere you will remember later, such as `/var/www/linguard`.
3. Move the files inside `/var/www/linguard/config` to `/var/www/linguard` and remove `.sample` from their names.
4. Edit the configuration files to fit your needs.
5. Start linguard:
    ```bash
    uwsgi --yaml /var/www/linguard/uwgsi.yaml
    ```

### Debian package

### Docker

## Docs

### Configuration

Two sample configuration files are provided: `linguard.sample.yaml` and `uwgsi.sample.yaml`.
However, the most interesting one is the first, since the second only contains options
for a third party software, [uWGSI](https://uwsgi-docs.readthedocs.io/en/latest/).

Hence, we will only discuss Linguard's configuration values here. Although the file `linguard.sample.yaml`
contains every possible option, the following tables explain each one of them and detail
all possible values.

#### Logging configuration

These options must be specified inside a `logger` node.

| Option | Explanation | Values | Default |
|-|-|-|-|
| _level_ | Set the minimum level of messages to be logged. | `debug`, `info`, `warning`, `error`, `fatal` | `info`
| _logfile_ | Path to the file used to write log messages. | `null`, `path/to/logfile` | `null`
| _overwrite_ | Whether to overwrite the log file when the application starts or not. | `true`, `false` | `false`

#### Web configuration

These options must be specified inside a `web` node.

| Option | Explanation | Values | Default |
|-|-|-|-|
| _bindport_ | Port to be used by Flask to deploy the application. | `1-65535` | `8080`
| _login_attempts_ | Maximum number of login attempts within 5 minutes. | (almost) Any integer. | `0` (unlimited attempts)

#### Linguard configuration

These options must be specified inside a `linguard` node.

##### Global options

| Option | Explanation | Values | Notes |
|-|-|-|-|
| _endpoint_ | Endpoint for all peers. | Should be something like `vpn.example.com`, though it may also be an IP address. | Default value is your computer's public IP (if it can be obtained).
| _gw_iface_ | Default gateway for all WireGuard interfaces. | Should be something like `vpn.example.com`, though it may also be an IP address. | Default value is your computer's public IP (if can be obtained).
| _wg_bin_ | Path to the WireGuard binary file (`wg`). | `path/to/file` | If not specified, it will be retrieved using the `whereis` command.
| _wg_quick_bin_ | Path to the WireGuard quick binary file (`wg-quick`). | `path/to/file` | If not specified, it will be retrieved using the `whereis` command.
| _interfaces_ | Dictionary containing all interfaces of the server. | A number of `interface` nodes whose keys are their own UUIDs. |
| _interfaces_folder_ | Path to the directory where the interfaces' configuration files will be placed. | `path/to/folder` | It should be somewhere you will remember, like `/var/www/linguard/interfaces`.
| _iptables_bin_ | Path to the iptables binary file (`iptables`). | `path/to/file` | If not specified, it will be retrieved using the `whereis` command.

##### Interface configuration

These options must be specified inside an `interface` node.

| Option | Explanation | Values | Notes |
|-|-|-|-|
| _auto_ | Whether the interface will be automatically brought up when the server starts or not. | `true`, `false` | Default value is `true`.
| _conf_file_ | Path to the interface's configuration file used by WireGuard. | `path/to/file` | If not specified, it will be generated in the `interfaces_folder`.
| _description_ | A description of the interface. | A character string |
| _gw_iface_ | Gateway used by the interface. | Should be something like `vpn.example.com`, though it may also be an IP address. | Default value is your computer's public IP (if it can be obtained).
| _ipv4_address_ | IPv4 address assigned to the interface. | A valid IPv4 address. |
| _listen_port_ | UDP port used by WireGuard to communicate with peers. | `1-65535` |
| _name_ | The interface's name. | A character string | It may only contain alphanumeric characters, underscores and hyphens. It must also begin with a letter and cannot be more than 15 characters long.
| _on_up_ | Linux commands to be executed when the interface is going to be brought up. | Any linux command in path. | By default, it will add FORWARD and POSTROUTING rules related to the interface.
| _on_down_ | Linux commands to be executed when the interface is going to be brought down. | Any linux command in path. | By default, it will remove FORWARD and POSTROUTING rules related to the interface.
| _peers_ | Dictionary containing all peers of the interface. | A number of `peer` nodes whose keys are their own UUIDs. |
| _private_key_ | Private key used to authenticate the interface. | A valid private key generated via `wg`. | 
| _public_key_ | Public key used to authenticate the interface. | A valid private key generated via `wg`. |
| _uuid_ | Unique identifier. | A valid Version 4 UUID. |

##### Peer configuration

These options must be specified inside a `peer` node.

| Option | Explanation | Values | Notes |
|-|-|-|-|
| _dns1_ | Main DNS used by the peer. | `1-65535` |
| _dns2_ | Secondary DNS used by the peer. | `1-65535` |
| _endpoint_ | URL/IPv4 and port used by the peer to communicate with the WireGuard server. | A valid URL/IPv4 followed by a UDP port: `vpn.example.com:50000` | 
| _ipv4_address_ | IPv4 address assigned to the peer. | A valid IPv4 address. |
| _name_ | The peer's name. | A character string
| _nat_ | Whether the peer is behind a NAT or not. | `true`, `false` | Default value is `false`. If `true`, this option will enable the `PersistentKeepalive` WireGuard flag.
| _private_key_ | Private key used to authenticate the peer. | A valid private key generated via `wg`. | 
| _public_key_ | Public key used to authenticate the peer. | A valid private key generated via `wg`. |
| _uuid_ | Unique identifier. | A valid Version 4 UUID. |

### Classes

## Notes

### Changelog

### Known issues

## Contributing

You may contribute opening issues and creating pull requests with new features and bugfixes :)