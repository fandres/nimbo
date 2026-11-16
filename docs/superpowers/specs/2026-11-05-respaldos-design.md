# Respaldo y restauración de Nimbo

## Objetivo
Recuperar en conjunto los registros y sus documentos, desde Configuración, con verificación y una copia de seguridad del estado anterior.

## Enfoques
- Copiar solamente SQLite: sencillo, pero incompleto porque los adjuntos están fuera de la base.
- Archivo único portable: opción propuesta y aceptada para esta etapa; incluye base, documentos y configuración del negocio. Facilita traslado Linux/Windows y recuperación.
- Sincronización en nube: fuera del alcance actual.

## Pantalla
Nueva sección «Copias de seguridad» en Configuración con Crear respaldo, Restaurar respaldo, carpeta automática y estado del último respaldo correcto o fallido. Mostrar fecha, ubicación y si incluye documentos. Se permite abrir la carpeta desde la aplicación.

## Contenido
Archivo ZIP con manifiesto propio de Nimbo, versión de formato, versión del programa, versión de esquema, fecha, inventario de archivos con tamaños y SHA-256. Incluye una instantánea consistente de SQLite mediante su API de backup, toda la carpeta Documentos (incluidas copias conservadas en historial), logo si existe y una lista explícita de preferencias del negocio. No copiar archivos temporales, bloqueos, WAL/SHM, otros respaldos ni rutas particulares del equipo. Las preferencias del destino y frecuencia de respaldos permanecen locales al equipo.

Durante la instantánea se bloquean temporalmente las operaciones que modifican registros, adjuntos, logo o preferencias para conservar la consistencia del conjunto. Mostrar progreso y evitar una segunda operación de respaldo/restauración simultánea.

Al faltar un adjunto vigente referenciado, rechazar la creación como respaldo completo e informar cuál falta; no anunciar éxito con documentos perdidos. El archivo se construye temporalmente y solo se publica al terminar su validación. No sobrescribir un respaldo existente de forma implícita.

## Restauración
1. Seleccionar el archivo y examinarlo sin alterar datos actuales.
2. Validar formato, tamaños, hashes, integridad y relaciones de SQLite, rutas y documentos. Rechazar rutas que escapen de la carpeta, enlaces, entradas duplicadas, archivos inesperados y versiones de esquema más nuevas que la aplicación. Establecer límites explícitos y mensajes de error para archivos excesivos.
3. Mostrar fecha y versión del respaldo, cantidad de documentos y advertencia de que reemplaza los datos actuales, sin mezclar registros. Pedir confirmación; impedir restaurar con formularios abiertos sin guardar.
4. Crear y verificar automáticamente un respaldo completo del estado actual. Si falla, no restaurar.
5. Preparar los datos entrantes en una carpeta temporal y efectuar el reemplazo con la conexión SQLite cerrada y bloqueo de instancia mantenido. Usar un registro de recuperación persistente para poder deshacer una interrupción entre la sustitución de base, documentos, logo y preferencias. Ninguna ventana podrá seguir trabajando con la conexión anterior.
Los archivos preparados y originales de recuperación se mantienen en el mismo volumen que los datos. Un punto de confirmación persistente distingue dos estados: antes de confirmar, el siguiente arranque revierte todos los componentes; después, conserva el conjunto restaurado. No eliminar originales antes de confirmar.

6. Cerrar la aplicación al terminar y solicitar volver a abrir Nimbo. Al arrancar, resolver cualquier restauración interrumpida antes de abrir SQLite. Conservar el respaldo previo y reportar el resultado.

## Respaldo automático
Propuesta inicial: desactivado hasta elegir carpeta y habilitarlo. Al abrir Nimbo, crear como máximo uno por día local cuando la opción esté activa. No exige que la aplicación permanezca abierta ni depende del programador de tareas del sistema. Si falla, mostrar aviso y no bloquear el uso normal. No eliminar respaldos automáticamente en esta primera implementación. Recomendar seleccionar una unidad distinta, sin imponerla.

## Compatibilidad
Normalizar las rutas relativas de adjuntos para traslado entre Windows y Linux, validándolas antes de copiarlas o resolverlas.

Reutilizar la identidad y ubicación persistentes actuales. La validación no debe ejecutar SQL ni código suministrado por un manifiesto. Los respaldos anteriores de migración (.backup-...) siguen conservados; esta interfaz utiliza el nuevo formato completo. Las bases antiguas compatibles se migran en un entorno temporal validado antes de reemplazar el estado actual.

## Pruebas necesarias
- Crear respaldo, modificar una base temporal, restaurar y verificar registros, importes, preferencias y adjuntos byte a byte.
- Base con WAL, documentos vacíos, adjuntos retirados y logo ausente.
- Archivo corrupto, hash incorrecto, documento faltante, rutas maliciosas, esquema más nuevo y límite de tamaño.
- Fallos de permisos/espacio, fallo al crear respaldo previo y fallo entre pasos de reemplazo: conservar o recuperar el estado anterior.
- Respaldo automático una vez al día, deshabilitado y errores visibles.
- Pruebas en datos temporales; no restaurar sobre la base real del usuario durante el desarrollo.

## Aprobación
Diseño aprobado por el usuario, incluyendo el respaldo automático diario al abrir y la reapertura del programa tras restaurar. No incluye cifrado, contraseña, nube ni limpieza automática de respaldos.

## Revisión de viabilidad
Revisión independiente completada: incorporadas consistencia entre SQLite/archivos/preferencias y recuperación con punto de confirmación persistente en el mismo volumen.
