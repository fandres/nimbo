# Copias de seguridad de Nimbo

En **Configuración → Copias de seguridad** puedes guardar un respaldo completo o restaurarlo.

## Crear
Pulsa **Crear respaldo** y elige un nombre nuevo y una carpeta. El ZIP incluye la base de datos, toda la carpeta de documentos (incluidas copias históricas), el logo y las preferencias portables del negocio. Se comprueba su contenido antes de anunciar éxito. Si falta un adjunto vigente, se muestra el archivo faltante y no se crea un respaldo incompleto.

No se incluyen otros respaldos ni archivos temporales de SQLite. El archivo no está cifrado: contiene los registros y documentos del negocio. Conserva las copias en una ubicación bajo tu control.

## Automático
Elige una carpeta y activa **Crear un respaldo al abrir Nimbo, como máximo una vez al día**. Está desactivado por defecto. No ejecuta tareas cuando Nimbo está cerrado y no elimina copias antiguas. Una copia manual correcta también cuenta para ese día. Ante un fallo, Nimbo avisa y permite continuar trabajando.

## Restaurar
Guarda o descarta las ediciones pendientes y cierra los formularios. Pulsa **Restaurar respaldo**, selecciona un ZIP creado por esta función y revisa la fecha, versión y cantidad de documentos antes de confirmar.

La restauración reemplaza el conjunto de datos; no combina registros. Antes se crea una copia completa del estado actual en **Respaldos**, dentro de la carpeta de datos de Nimbo. Si esa copia falla, no se sustituye nada. La base entrante se verifica y se migra en una copia temporal si corresponde.

Nimbo cierra su conexión a la base antes de cambiar los archivos y conserva el bloqueo de instancia. Al terminar se cierra el programa: vuelve a abrirlo. Una restauración interrumpida antes de confirmarse se revierte al siguiente arranque; una ya confirmada conserva los datos restaurados.

Las preferencias de carpeta y activación de respaldos siguen perteneciendo al equipo actual. Las copias antiguas `.backup-...` creadas por migraciones son solo bases de datos: no son ZIP completos de esta función.

## Límites de esta versión
Formato 1; máximo 100000 archivos, 2 GiB por archivo y 8 GiB descomprimidos. No admite enlaces simbólicos, rutas no portables ni bases de versiones más nuevas. Los respaldos sin documentos son válidos. La verificación usa SHA-256 para detectar alteraciones, no para autenticar al creador del archivo.

## Validación del desarrollo
Pruebas con bases temporales: creación/restauración, WAL, archivos corruptos, rutas inseguras, versión incompatible, base incompleta, documentos faltantes, fallo de la copia previa, fallo de preferencias, interrupciones antes y después de confirmar, copia diaria y bloqueo de cambios sin guardar. Se probaron fallos simulados de proceso y E/S; no se simuló un corte físico de energía.
