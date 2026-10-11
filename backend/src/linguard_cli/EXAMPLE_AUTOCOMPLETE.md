# Ejemplos de Autocompletado Linguard CLI

## 🎯 Introducción

El sistema de autocompletado de Linguard CLI te ayuda a configurar rápidamente tu red WireGuard sin tener que recordar direcciones IP, rangos de subnets, servidores DNS y más.

## 📦 Instalación

```bash
cd backend/src/linguard_cli
pip install -e .
```

## 🚀 Comandos de Autocompletado

### 1. Sugerencias de Direcciones IP

```bash
# Mostrar sugerencias generales de IPs
linguard completers ip

# Mostrar 20 sugerencias
linguard completers ip -c 20

# Sugerencias con prefijo específico
linguard completers ip 192.168.1

# Sugerencias de IPs privadas
linguard completers ip 10.0.0

# Sugerencias de IPs públicas de prueba
linguard completers ip 203.0.113
```

**Salida de ejemplo:**
```
Suggested IP addresses:
  1. 192.168.1.1
  2. 192.168.1.2
  3. 192.168.1.3
  4. 10.0.0.1
  5. 10.0.0.2
  6. 172.16.0.1
  7. 203.0.113.1
  8. 8.8.8.8
  9. 1.1.1.1
```

### 2. Sugerencias de Subnets

```bash
# Mostrar rangos de subnets comunes
linguard completers subnet

# Sugerencias de subnets desde una red específica
linguard completers subnet 192.168.1.0

# Sugerencias con clase específica
linguard completers subnet --class A
linguard completers subnet --class B
linguard completers subnet --class C
```

**Salida de ejemplo:**
```
Common subnet ranges:
  192.168.1.0/24 - Class C - 254 hosts
  192.168.0.0/16 - Class C - 65534 hosts
  10.0.0.0/8 - Class A - 16M hosts
  172.16.0.0/12 - Class B - 1M hosts
```

### 3. Sugerencias de DNS

```bash
# Mostrar todos los servidores DNS
linguard completers dns

# DNS de Cloudflare
linguard completers dns --provider cloudflare

# DNS de Google
linguard completers dns --provider google

# DNS de Quad9
linguard completers dns --provider cloud
```

**Salida de ejemplo:**
```
Suggested DNS (cloudflare):
  1.1.1.1
  1.0.0.1
  2606:4700:4700::1111
  2606:4700:4700::1001
```

### 4. Sugerencias de Puertos

```bash
# Mostrar puertos WireGuard comunes
linguard completers port

# Sugerencias de rango de puertos
linguard completers port -r 51820-65535

# Puertos específicos
linguard completers port -r 443-8443
```

**Salida de ejemplo:**
```
Common WireGuard ports:
  51820
  51821
  51822
  443
  8443
  8080
```

### 5. Sugerencias de Nombres de Peers

```bash
# Mostrar nombres de peers comunes
linguard completers peer

# Con puerto específico del servidor
linguard completers peer --server-port 51820
```

**Salida de ejemplo:**
```
Suggested peer names:
  1. Office Network
  2. Home Device
  3. Mobile Hotspot
  4. Backup Server
  5. Development Machine
  6. Production Server
  7. IoT Device
  8. Remote Worker
```

## 🔧 Uso en Comandos Principales

### Crear Servidor con Autocompletado

```bash
# Sugerir IPs, DNS y puertos
linguard servers create --suggest-ip --suggest-dns --suggest-port \
  --name "Production Server" --endpoint vpn.example.com

# Usar sugerencias específicas
linguard servers create \
  --name "Prod Server" \
  --port 51820 \
  --endpoint vpn.example.com \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart
```

### Crear Peer con Autocompletado

```bash
# Sugerir rango de IPs
linguard peers create 1 --suggest-range \
  --name "Office Network" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# Crear peer con parámetros específicos
linguard peers create 1 \
  --name "Home Device" \
  --endpoint 203.0.113.50 \
  --allowed-ips 192.168.1.0/24 \
  --ipv6 fd00::100/128 \
  --preshared-key "your-key-here"
```

### Ejemplos Prácticos

#### Escenario 1: Configurar Servidor de Producción

```bash
# 1. Ver sugerencias disponibles
linguard completers ip
linguard completers dns --provider cloudflare
linguard completers port

# 2. Crear servidor con sugerencias
linguard servers create \
  --name "Production VPN" \
  --suggest-ip \
  --suggest-dns \
  --suggest-port \
  --endpoint vpn.company.com

# 3. Especificar configuración final
linguard servers create \
  --name "Production VPN" \
  --port 51820 \
  --endpoint vpn.company.com \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart \
  --description "Main production WireGuard server"
```

#### Escenario 2: Añadir Peers a la Red

```bash
# 1. Ver rangos de subnets disponibles
linguard completers subnet

# 2. Crear peer de oficina
linguard peers create 1 \
  --name "Office Network" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# 3. Crear peer de casa
linguard peers create 1 \
  --name "Home Device" \
  --endpoint 203.0.113.50 \
  --allowed-ips 192.168.2.0/24 \
  --ipv6 fd00::200/128

# 4. Crear peer de backup
linguard peers create 1 \
  --name "Backup Server" \
  --endpoint 10.0.0.50 \
  --allowed-ips 192.168.3.0/24
```

#### Escenario 3: Configurar Red Completa

```bash
# Paso 1: Crear servidor principal
linguard servers create \
  --name "Main VPN" \
  --port 51820 \
  --endpoint vpn.local \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart

# Paso 2: Configurar peer de oficina
linguard peers create 1 \
  --name "Office" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# Paso 3: Configurar peer de desarrollo
linguard peers create 1 \
  --name "Dev Machine" \
  --endpoint 192.168.1.101 \
  --allowed-ips 192.168.1.0/24 \
  --preshared-key "dev-key-12345"

# Paso 4: Ver configuración
linguard servers list
linguard peers list
```

## 💡 Consejos y Mejores Prácticas

### 1. Combinar Autocompletado con Parámetros Específicos

```bash
# Ver sugerencias primero
linguard completers ip
linguard completers subnet

# Luego usar en el comando
linguard servers create \
  --name "MyServer" \
  --port 51820 \
  --endpoint vpn.example.com \
  --ipv4 10.0.0.1/24 \
  --dns-primary 1.1.1.1
```

### 2. Usar --suggest para Interactividad

```bash
# El CLI te mostrará sugerencias y te pedirá confirmación
linguard servers create --suggest-ip \
  --name "Server" \
  --endpoint example.com

# Te mostrará opciones como:
# 1. 10.0.0.1/24
# 2. 192.168.1.0/24
# 3. 172.16.0.0/12
# (Enter to skip)
```

### 3. Guardar Configuraciones Reutilizables

```bash
# Crear un script para configuraciones estándar
cat > create_server.sh << 'EOF'
#!/bin/bash
linguard servers create \
  --name "$SERVER_NAME" \
  --port "$SERVER_PORT" \
  --endpoint "$SERVER_ENDPOINT" \
  --ipv4 10.0.0.$((RANDOM % 255))/24 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart
EOF

chmod +x create_server.sh
```

### 4. Usar DNS Seguros

```bash
# DNS seguro de Cloudflare
linguard servers create \
  --name "Secure Server" \
  --port 51820 \
  --endpoint vpn.example.com \
  --dns-primary 1.0.0.1 \
  --dns-secondary 1.1.1.1

# DNS de Google
linguard servers create \
  --name "Google DNS" \
  --port 51820 \
  --endpoint vpn.example.com \
  --dns-primary 8.8.8.8 \
  --dns-secondary 8.8.4.4
```

## 🔍 Solución de Problemas

### Problema: Las sugerencias no aparecen

**Solución:**
```bash
# Verificar que la CLI esté instalada
linguard --version

# Verificar permisos
ls -la linguard

# Reiniciar autocompletado
linguard completers ip
```

### Problema: Las IPs sugeridas no son válidas

**Solución:**
```bash
# Verificar las sugerencias manualmente
linguard completers ip --count 10

# Usar rangos conocidos
linguard completers subnet --class C
```

### Problema: DNS no se conecta

**Solución:**
```bash
# Verificar DNS disponibles
linguard completers dns

# Usar DNS público confiable
linguard servers create \
  --name "Test" \
  --port 51820 \
  --endpoint example.com \
  --dns-primary 1.1.1.1
```

## 📚 Recursos Adicionales

- [Documentación completa](README.md)
- [Guía de usuario](GUIDE.md)
- [API Reference](http://localhost:8000/docs)

## 🎓 Aprendizaje

### Nivel Básico

```bash
# Ver todas las opciones
linguard completers --help

# Usar sugerencias básicas
linguard servers create --suggest-ip --name "Test" --endpoint test.com
```

### Nivel Intermedio

```bash
# Combinar múltiples sugerencias
linguard servers create --suggest-ip --suggest-dns --suggest-port \
  --name "Prod" --endpoint vpn.com

# Usar subnets específicas
linguard completers subnet 192.168.1.0
```

### Nivel Avanzado

```bash
# Script con autocompletado
cat > deploy_vpn.sh << 'EOF'
#!/bin/bash
# Sugerir IPs para servidor
linguard completers ip > /tmp/ip_suggestions.txt

# Sugerir DNS
linguard completers dns --provider cloudflare > /tmp/dns.txt

# Usar sugerencias
SERVER_IP=$(head -1 /tmp/ip_suggestions.txt)
DNS_PRIMARY=$(head -1 /tmp/dns.txt)

linguard servers create \
  --name "Auto Deploy" \
  --port 51820 \
  --endpoint vpn.example.com \
  --ipv4 $SERVER_IP \
  --dns-primary $DNS_PRIMARY
EOF

chmod +x deploy_vpn.sh
```

## 🏆 Ejemplo de Configuración Óptima

```bash
#!/bin/bash

# Configuración completa de servidor VPN

# 1. Crear servidor principal
linguard servers create \
  --name "Production VPN" \
  --port 51820 \
  --endpoint vpn.company.com \
  --ipv4 10.0.0.1/24 \
  --ipv6 fd00::1/64 \
  --dns-primary 1.1.1.1 \
  --dns-secondary 8.8.8.8 \
  --autostart \
  --description "Main production WireGuard server"

# 2. Configurar peer de oficina
linguard peers create 1 \
  --name "Office Network" \
  --endpoint 192.168.1.100 \
  --allowed-ips 192.168.1.0/24

# 3. Configurar peer de desarrollo
linguard peers create 1 \
  --name "Dev Machine" \
  --endpoint 192.168.1.101 \
  --allowed-ips 192.168.1.0/24 \
  --preshared-key "dev-key-secure-12345"

# 4. Crear backup
linguard backups create --name "pre-config-backup"

# 5. Verificar configuración
linguard servers list
linguard peers list
linguard status health
```

---

**Versión:** 0.1.0  
**Última actualización:** 2024-10-11
