# Requisitos para la primera beta de Nimbo

## Una sola instancia por base de datos

Solicitud del usuario: 21 de octubre de 2026. Implementado en el código el 23 de octubre de 2026.

Impedir que dos procesos de Nimbo trabajen simultáneamente sobre la misma base.
Adquirir un bloqueo de proceso antes de abrir o migrar SQLite y conservarlo hasta
cerrar el programa. Ante una segunda apertura, activar la ventana existente si
es posible; en su defecto, avisar que Nimbo ya está abierto y salir sin tocar la base.

Resolver la ruta real de la base para que accesos directos o rutas equivalentes no
eludan el bloqueo. Recuperar bloqueos de procesos terminados de forma segura; no
eliminar un bloqueo que pertenezca a una instancia activa. Comprobar también
lanzamientos simultáneos y recuperación tras un cierre inesperado.

Validar en Debian 13 y Windows 11, tanto desde el script como desde los paquetes.
Mantener además transacciones y controles de revisión: el bloqueo de instancia
no sustituye esas protecciones ni las copias de seguridad.

## Implementación y alcance

Se usa `QLockFile` sobre `catalog.sqlite3.lock`, con la ruta canónica de la base.
La segunda apertura avisa «Nimbo ya está abierto» y sale antes de acceder a SQLite.
El bloqueo se mantiene hasta cerrar el repositorio y no caduca por antigüedad;
Qt permite recuperar el bloqueo si su proceso propietario terminó.

Es una protección cooperativa para bases locales: las versiones anteriores de
Nimbo y programas externos que abran SQLite no participan en este bloqueo.
No se modifican el esquema ni los datos. `--version` no abre la base y
`--smoke-test` usa una base temporal con el mismo mecanismo de bloqueo.

Los AppImage y ZIP de alfa 0.2 publicados previamente no se han reconstruido.
Queda pendiente probar los nuevos paquetes en equipos reales con Debian 13 y
Windows 11 cuando se prepare la siguiente distribución.

Verificación de código: 229 pruebas aprobadas en Linux local, Debian 13 y
Python para Windows bajo Wine; incluye lanzamientos simultáneos y recuperación
tras un cierre inesperado. Wine no sustituye la prueba en Windows 11 real.

## Preparación actualizada · 6 de noviembre de 2026

- Informes de Ventas, Gastos y Dinero implementados en código (commit 17f00f9),
  además de respaldos completos y restauración (f412711).
- FIFO automático e informe de Rentabilidad implementados (92710dc).
  Método configurable pospuesto a una versión posterior.
- Antes de etiquetar beta 1: validar migración desde la alfa distribuida, respaldo
  y restauración de base/documentos, y ciclo compra → recepción → venta → edición
  / anulación sin descuadres de cantidades ni costos.
- Compilar paquetes nuevos y comprobarlos en Debian 13 y Windows 11 reales. Las
  pruebas anteriores de otras versiones no sustituyen estas verificaciones.
- Delimitar y publicar las funciones incluidas y limitaciones. Contraseña opcional,
  códigos de barras y lectura de facturas siguen pendientes; no presentarlos como
  implementados. Revisar si alguno debe entrar antes de distribuir la beta.

## Validación de preparación · 7 de noviembre de 2026

Se trabajó exclusivamente con datos de prueba en carpetas temporales.

- Migración desde una base creada con las fuentes distribuidas de alfa 0.4:
  esquema 24 → 25. Conserva compra, recepción, venta y existencias; genera copia
  previa de SQLite. `integrity_check` y `foreign_key_check` correctos.
- Esa venta histórica conserva costo FIFO y resultado correctos tras actualizar.
- Prueba de integración permanente: compra con gastos → recepción → venta →
  reducción de cantidad → corrección tardía de gastos → respaldo completo →
  anulación → restauración. Coinciden stock, costo y resultado anteriores al
  respaldo; se recupera la copia del documento aunque se eliminó el original.
- Suite final: 467 pruebas aprobadas en Linux local (16,53 s), Debian 13
  aislado (20,05 s) y Python/Qt Windows bajo Wine (30,80 s). Smoke local correcto.
  Esto no sustituye la validación de paquetes en Windows 11 real.

### Antes de distribuir beta 1

1. Preparar AppImage y ZIP Windows con el código actual, fuentes y avisos de
   licencia; verificar manifiestos, versiones y hashes de los nuevos paquetes.
2. Probar esos paquetes con datos de prueba: abrir/cerrar, segunda instancia,
   formularios, adjuntos, PDF, respaldo y restauración. En Windows 11 la prueba
   debe hacerse también en un sistema real; Wine no acredita esa compatibilidad.
3. Validar en ambos equipos una copia de los datos antes de usar la beta con
   registros definitivos. No abrir la alfa antigua sobre la base actualizada.

La validación del código no equivale a haber generado ni aprobado los nuevos
binarios. Se mantienen pendientes contraseña opcional, códigos de barras y
lectura automática de facturas, tal como constan en futuras versiones.

### Corrección detectada durante la validación

El autocompletado de proveedor por alias se normaliza después de que Qt inserta
la sugerencia. Así Windows no vuelve a reemplazar el nombre real por la etiqueta
«alias · proveedor». Regresión comprobada con Tab, selección por clic y alias.
La ejecución con Qt Windows (plataforma windows bajo Wine) aprobó esas 4 pruebas.

Para la suite sin escritorio bajo Wine, configurar `QT_QPA_PLATFORM=offscreen`
y `QT_QPA_FONTDIR` dentro del proceso Python si el lanzador no conserva variables
externas. Dos fallos iniciales de selección provenían de ejecutar la ruta para
mouse de escritorio en lugar de la ruta offscreen; no se alteraron esas pruebas.

## Distribución 0.5.0-beta.1 · 7 de noviembre de 2026

Paquetes generados en `dist/`:

- `Nimbo-0.5.0-beta.1-linux-x86_64.AppImage` (Debian 13).
- `Nimbo-0.5.0-beta.1-windows-x86_64.zip` (herramientas Windows bajo Wine).
- `Nimbo-0.5.0-beta.1-sources.zip` (Nimbo MIT y fuentes de dependencias).

468 pruebas aprobadas: Linux local (16,48 s), Debian 13 aislado (20,68 s),
Windows/Qt bajo Wine (30,97 s). Los dos paquetes pasan su prueba de arranque
con base temporal. AppImage confirma la versión dentro de Debian 13. Manifiestos
JSON y SHA256 acompañan a los binarios; las 79 entradas del inventario de
bibliotecas Debian coinciden con las fuentes incluidas. El ZIP no contiene bases
comerciales. Incluye guía LEEME-beta, licencias y sustitución de bibliotecas.

La prueba de escritorio con esta beta en equipos reales Debian 13 y Windows 11
queda pendiente del usuario. Antes de actualizar, guardar un respaldo completo
(base y documentos); no abrir la alfa antigua sobre la base migrada. No se ha
publicado en GitHub ni se ha firmado digitalmente el ejecutable Windows.
