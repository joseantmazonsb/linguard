# Firewall Configuration

## Overview

Linguard requires firewall support to manage WireGuard interfaces effectively. The firewall system uses iptables (Linux) to enforce network policies.

## Requirements

### Linux Systems

- **iptables** or **nftables** must be installed
- **Passwordless sudo** must be configured for firewall commands
- Root access or equivalent privileges required

### Configuration

Create a sudoers file at `/etc/sudoers.d/linguard`:

```bash
yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables
```

Or with the `-n` flag for non-interactive mode:

```bash
yourusername ALL=(ALL) NOPASSWD: /sbin/iptables -n, /sbin/ip6tables -n
```

**Important:** The sudoers file must have permissions `440`:

```bash
chmod 440 /etc/sudoers.d/linguard
```

## Testing

Verify the configuration works:

```bash
# Test iptables command
sudo iptables --list

# Or with passwordless sudo
echo "yourpassword" | sudo -S iptables --list
```

## Firewall Services

Linguard includes the following firewall-related services:

### Firewall Service (`app/services/firewall/service.py`)

Main service that manages firewall operations and driver detection.

### iptables Driver (`app/services/firewall/iptables_driver.py`)

Linux-specific firewall driver that:
- Runs iptables commands with timeout protection
- Prevents password prompts using `SUDO_ASKPASS`
- Handles non-interactive mode with `-n` flag
- Validates command execution

### Firewall Bypass (Development Only)

During development, you can bypass firewall requirements:

```bash
export DEBUG_BYPASS_FIREWALL=true
```

**WARNING:** Never use this in production!

## Troubleshooting

### "iptables requires passwordless sudo"

**Error:** The firewall service cannot execute iptables commands without password.

**Solution:**
1. Create the sudoers file:
   ```bash
   echo "yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables" | \
   sudo tee /etc/sudoers.d/linguard > /dev/null
   chmod 440 /etc/sudoers.d/linguard
   ```

2. Test the configuration:
   ```bash
   sudo -l | grep linguard
   ```

### "Command requires password"

**Error:** The iptables command is prompting for a password.

**Solution:** Ensure your sudoers rule includes the exact command being run. The backend may add flags like `-n` automatically, so your rule should cover both:

```bash
yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/iptables -n
```

Or better, allow all iptables commands:

```bash
yourusername ALL=(ALL) NOPASSWD: /sbin/iptables, /sbin/ip6tables, /usr/bin/wg-quick, /usr/bin/wg
```

## Security Notes

1. **Least Privilege:** Only grant the minimum permissions needed for iptables commands
2. **Regular Audits:** Review sudoers configuration periodically
3. **Production:** Never use password bypass in production environments
4. **Logs:** Monitor sudo logs for unauthorized access attempts

## Additional Drivers

Linguard supports multiple firewall drivers. The system automatically detects and uses the available one:

- **iptables** (default for Linux)
- **nftables** (alternative for modern Linux distributions)
- **Firewalld** (for systems using firewalld)

The driver detection happens during service startup. If no supported driver is found, the firewall service will exit with an error.
