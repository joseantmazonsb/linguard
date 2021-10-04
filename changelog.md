# Changelog

- Management of **Wireguard** interfaces and peers via web. Interfaces can be created, removed, edited, exported and brought up and down directly from the web GUI. Peers can be created, removed, edited and downloaded at anytime as well.
- Added `linguard` systemd service.
- Display stored and real time traffic data using charts (storage of traffic data may be disabled).
- Display general network information.
- Logging to file or stdout.
- Autodetect `wireguard` and `iptables` binaries if not present in configuration file.
- Autodetect endpoint if not present in configuration file (uses public ip).
- Ability to change the location of the interfaces' files.
- Ask to create an admin account if there isn't one.
- Encrypted user credentials (AES).
- Ability to change admin password.