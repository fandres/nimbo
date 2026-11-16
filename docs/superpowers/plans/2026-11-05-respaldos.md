# Respaldo y restauración Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task.

**Goal:** Respaldo completo verificable y restauración recuperable desde Configuración.
**Architecture:** Servicio independiente de Qt para ZIP/manifiesto/SQLite y carpeta de preparación con diario; adaptador de preferencias; página Qt y coordinación del ciclo de vida en app.py. Restaurar solo después de cerrar la conexión y antes de liberar el bloqueo.
**Tech Stack:** Python estándar (sqlite3, zipfile, hashlib, json), PySide6.
**Spec:** docs/superpowers/specs/2026-11-05-respaldos-design.md

## Restricciones
Preservar datos antes de restaurar; archivo único base/documentos/logo/preferencias; auto diario opt-in; no nube ni cifrado; datos temporales para pruebas. No copiar rutas o configuración de respaldos entre equipos.

## Pasos
- [x] Pruebas fallidas y servicio backup_archive.py: copia SQLite consistente, manifiesto SHA256, validación de ZIP/rutas/versiones/archivos, preparar base migrada temporal.
- [x] Servicio backup_restore.py: original+entrante en mismo volumen, diario persistente y rollback al arrancar; pruebas de fallos por cada paso y preferencias.
- [x] Preferencias portables/automáticas y BackupPage en Configuración; coordinación de cierre/restauración y recuperación antes de abrir SQLite, auto diario al arrancar.
- [x] Pruebas de integración y suite completa; inspección visual, revisión independiente, documentación y commit.

## Decisiones de implementación
- Límites: 2 GiB por archivo, 8 GiB descomprimidos, 100000 entradas, manifiesto máximo 16 MiB. Rechazo explícito al excederlos.
- Preferencias portables: cinco booleanos ya existentes (visualización mensual de compras, identificación del cliente, IVA por defecto en ventas/compras, documentos de retención). Configuración financiera ya reside en SQLite.
- Creación y preparación sin procesar eventos de usuario durante copia para impedir mutaciones concurrentes desde Qt; cursor de espera y mensaje de operación. No hay hilos modificadores en la aplicación actual.
- Respaldo previo a restauración obligatorio en subcarpeta Respaldos del directorio de datos; restauración pendiente no abre la interfaz hasta recuperación finalizada.
- Entregables actuales: código y pruebas, no nueva compilación de binarios.

## Registro de validación
- Revisión independiente completada. Corregidas validación de estructura completa SQLite y detección de ajustes sin guardar; regresiones agregadas.
- Sincronización de archivos temporales ajustada para Windows (descriptor abierto con escritura).
- 20 pruebas de respaldos en Python para Windows bajo Wine aprobadas; prueba adicional de interrupción después del punto de confirmación agregada y validada en Linux.
- Suite Linux completa: 431 pruebas aprobadas; comprobación final de respaldos: 21 aprobadas.
- Pantalla revisada a 1100 × 700; arranque offscreen comprobado con datos temporales.
- No se tocaron los registros reales ni se recompilaron binarios.

Ruling: la restauración se aplica después de terminar el bucle de Qt y cerrar SQLite, aún dentro del bloqueo de instancia. Así no existen ventanas operando con la conexión anterior.
Ruling: se validan columnas y tipos de todas las tablas del esquema actual contra una base nueva de Nimbo; bases anteriores se comprueban nuevamente después de migrarlas en el área temporal.
