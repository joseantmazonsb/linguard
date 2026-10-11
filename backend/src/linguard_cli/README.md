# Linguard CLI

Command Line Interface para gestionar servidores WireGuard con Linguard.

## Características

- ✅ Gestión de servidores (crear, listar, eliminar, iniciar, detener)
- ✅ Gestión de peers (crear, listar, eliminar)
- ✅ Backup y restauración
- ✅ Verificación de estado del sistema
- ✅ Autenticación con tokens JWT
- ✅ Salida en formato JSON o texto

## Instalación

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

## Uso Rápido

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

## Ejemplos

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

## Salidas JSON

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
