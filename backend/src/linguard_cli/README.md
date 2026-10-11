# Linguard CLI

Command Line Interface para gestionar servidores WireGuard con Linguard.

## 🚀 Características

- ✅ Gestión completa de servidores WireGuard
- ✅ Gestión de peers con autocompletado de IPs
- ✅ Traffic triggers para monitoreo
- ✅ Integraciones y webhooks
- ✅ Backups y restauración
- ✅ Métricas y monitoreo
- ✅ Sistema de notificaciones
- ✅ **Autocompletado inteligente de IPs** (rangos privados, subnets)
- ✅ **Sugerencias de DNS** (Cloudflare, Google, Quad9)
- ✅ **Sugerencias de puertos** (WireGuard defaults, HTTPS)
- ✅ **Sugerencias de nombres de peers**
- ✅ **Sugerencias de subnets y rangos de IPs**
- ✅ Salidas formateadas en tablas
- ✅ Colores y formatting para mejor UX
- ✅ Salida JSON para automatización
- ✅ Autenticación JWT segura

## 📦 Instalación

### Método 1: Usar pip directamente

```bash
cd backend/src/linguard_cli
pip install -e .
```

### Método 2: Instalar desde linguard

```bash
cd backend
pip install -r requirements.txt
pip install -e src/linguard_cli
```

## Configuración

### Variables de Entorno

```bash
export LINGUARD_API_URL="http://localhost:8000"
export LINGUARD_API_TOKEN="your-jwt-token-here"
```

O crear un archivo `.env`:

```bash
LINGUARD_API_URL=http://localhost:8000
LINGUARD_API_TOKEN=your-jwt-token-here
```

## 📖 Documentación

Para una guía completa con ejemplos detallados, ver [GUIDE.md](GUIDE.md)

## 🎯 Comandos Rápidos

```bash
# Iniciar sesión
linguard auth login

# Listar servidores
linguard servers list

# Crear servidor
linguard servers create --name mi-servidor --port 51820 --endpoint vpn.ejemplo.com

# Listar peers
linguard peers list

# Crear peer
linguard peers create 1 --name mi-peer --endpoint 203.0.113.1

# Crear backup
linguard backups create

# Ver estado del sistema
linguard status system
```

## Comandos Disponibles

### Authentication

- `linguard auth login` - Iniciar sesión y obtener token
- `linguard auth status` - Ver estado de autenticación
- `linguard auth logout` - Eliminar token

### Servers

- `linguard servers list` - Listar todos los servidores
- `linguard servers create` - Crear nuevo servidor
- `linguard servers delete` - Eliminar servidor
- `linguard servers start` - Iniciar servidor
- `linguard servers stop` - Detener servidor
- `linguard servers reload` - Recargar configuración

### Peers

- `linguard peers list` - Listar todos los peers
- `linguard peers create` - Crear nuevo peer
- `linguard peers delete` - Eliminar peer

### Backups

- `linguard backups list` - Listar backups
- `linguard backups create` - Crear backup

### Status

- `linguard status system` - Info del sistema
- `linguard status health` - Health check

## 🛠️ Autocompletado Inteligente

El CLI incluye un sistema de autocompletado para facilitar la configuración de tu red.

### Comandos de Autocompletado

```bash
# Sugerencias de direcciones IP
linguard completers ip
linguard completers ip -c 20          # Mostrar 20 sugerencias
linguard completers ip 192.168.1      # Sugerencias con prefijo

# Sugerencias de subnets
linguard completers subnet
linguard completers subnet 192.168.1.0

# Sugerencias de DNS
linguard completers dns
linguard completers dns --provider cloudflare
linguard completers dns --provider google
linguard completers dns --provider cloud

# Sugerencias de puertos
linguard completers port
linguard completers port -r 51820-65535  # Rango de puertos

# Sugerencias de nombres de peers
linguard completers peer
linguard completers peer --server-port 51820
```

### Usar con --suggest

```bash
# Sugerir IPs automáticamente
linguard servers create --suggest-ip --name "Server" --endpoint example.com

# Sugerir rangos de IPs
linguard peers create 1 --suggest-range --name "Peer"

# Combinar sugerencias
linguard servers create --suggest-ip --suggest-dns --suggest-port \
  --name "Prod Server" --endpoint vpn.example.com
```

### Ejemplos Prácticos

```bash
# Ver sugerencias de IPs comunes
linguard completers ip

# Ver sugerencias de subnets privadas
linguard completers subnet

# Ver sugerencias de DNS Cloudflare
linguard completers dns --provider cloudflare

# Ver sugerencias de puertos WireGuard
linguard completers port

# Ver sugerencias de nombres de peers
linguard completers peer
```

## 🎯 Comandos Rápidos

```bash
# Iniciar sesión
linguard auth login

# Listar servidores con tabla
linguard servers list

# Crear servidor
linguard servers create --name "MyServer" --port 51820 --endpoint vpn.example.com

# Gestionar servidores
linguard servers start 1
linguard servers stop 1
linguard servers reload 1

# Gestionar peers
linguard peers create 1 --name "Office" --endpoint 192.168.1.100
linguard peers list

# Traffic triggers
linguard traffic-triggers list
linguard traffic-triggers create --name "Alert" --scope peer --peer-id 1 --direction combined --threshold-bytes 1000000 --window last_hour

# Integraciones
linguard integrations list
linguard integrations create --name "Slack" --type webhook --url "https://hooks.slack.com/xxx"

# Notificaciones
linguard notifications list
linguard notifications mark-all-read

# Métricas
linguard metrics traffic --scope global

# Estado del sistema
linguard status system
linguard status health
```

## 📁 Estructura del Proyecto

### Crear un servidor completo

```bash
linguard servers create \
  --name "Production Server" \
  --port 51820 \
  --endpoint "vpn.ejemplo.com" \
  --ipv4 "10.0.0.1/24" \
  --ipv6 "fd00::1/64" \
  --dns-primary "1.1.1.1" \
  --dns-secondary "8.8.8.8" \
  --autostart \
  --description "Production WireGuard Server"
```

### Gestionar servidores

```bash
# Listar servidores
linguard servers list

# Iniciar servidor
linguard servers start 1

# Detener servidor
linguard servers stop 1

# Recargar configuración
linguard servers reload 1
```

### Crear un peer

```bash
linguard peers create \
  1 \
  --name "Office Network" \
  --endpoint "192.168.1.100" \
  --allowed-ips "192.168.1.0/24" \
  --preshared-key "your-pre-shared-key"
```

## 📁 Estructura del Proyecto

```
backend/src/linguard_cli/
├── __init__.py           # Package initialization
├── __main__.py           # Entry point
├── main.py               # CLI implementation (1000+ lines)
├── requirements.txt      # Dependencies
├── setup.py             # Installation script
├── test_cli.py          # Basic syntax test
├── README.md            # This file
└── GUIDE.md             # Complete documentation
```

## 🎨 Mejoras de UX

Para obtener salidas en formato JSON, usa la opción `--json`:

```bash
linguard servers list --json
```

## Requisitos

- Python 3.8+
- Linguard FastAPI backend corriendo
- Token de autenticación válido

## Contribuir

1. Clona el repositorio
2. Crea una rama con tu feature
3. Implementa los cambios
4. Prueba tu código
5. Envía un Pull Request

## Licencia

MIT License - see LICENSE file
