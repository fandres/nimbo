# Una instancia por base Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline.

**Goal:** impedir una segunda apertura de la misma base antes de abrir SQLite.
**Architecture:** DatabaseInstanceLock encapsula QLockFile; main y smoke_test
adquieren el guard y lo liberan después del cierre del repositorio.
**Tech Stack:** Python, PySide6 QtCore, SQLite existente.
**Spec:** ../specs/2026-10-23-instancia-unica-design.md

## Global constraints
Sin dependencias nuevas, sin modificar datos personales ni esquema, no forzar desbloqueo.

## Review focus
Proceso muerto; doble arranque simultáneo; alias de ruta; permisos; excepciones al iniciar/cerrar.

## Tasks
- [x] Escribir tests/test_instance_lock.py y pruebas de arranque en tests/test_app.py;
  verificar que fallan antes de implementar el guard.
- [x] Crear instance_lock.py: DatabaseInstanceLock(database_path), acquire(), release(),
  context manager, InstanceAlreadyRunning y InstanceLockError. canonical database_path
  y lock_path accesibles para pruebas; QLockFile con tiempo de caducidad desactivado.
- [x] Integrar app.main y smoke_test; avisos distintos para ocupado y error real.
- [x] Verificar concurrencia con procesos, cierre inesperado, antigüedad del archivo,
  rutas canónicas, repositorio nunca abierto al fallar y liberación después de errores.
- [x] Ejecutar suite local/Debian13/Windows bajo Wine, revisión independiente,
  actualizar documentación y guardar en Git. Paquetes publicados sin reconstruir.

## Resultado de verificación — 23 de octubre de 2026

- Linux local: 229 pruebas aprobadas.
- Debian 13: 229 pruebas aprobadas.
- Python para Windows bajo Wine: 229 pruebas aprobadas.
- Revisión independiente: sin hallazgos importantes; 15 pruebas específicas aprobadas.
- Todas las pruebas utilizaron datos temporales; no se abrió la base del negocio.
- Registros de ejecución locales en `build/single-instance/` (no versionados).
- Paquetes anteriores sin reconstruir; validación nativa de nuevos paquetes pendiente.
