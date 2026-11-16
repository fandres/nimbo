# Una instancia por base de datos

Implementación del requisito ya solicitado para la primera beta, documentado en
`docs/releases/primera-beta.md`. Sin cambios de interfaz salvo el aviso de apertura.

## Enfoque

Usar QLockFile de QtCore, ya incluido, con la ruta canónica de la base y un archivo
adyacente `.lock`. Frente a un registro manual de PID, Qt aporta bloqueo nativo y
detección de procesos finalizados en Linux y Windows. Un servidor local permitiría
activar la ventana anterior, pero añade IPC y recuperación de sockets: se elige
el comportamiento ya autorizado de avisar y cerrar la segunda apertura.

Crear el directorio, resolver enlaces y normalizar la ruta antes de abrir SQLite.
Adquirir con `tryLock(0)` y `setStaleLockTime(0)`: nunca esperar indefinidamente ni
considerar abandonado un bloqueo por su antigüedad. Mantener el objeto hasta cerrar
el repositorio; liberar en finally, también si falla migración o creación de UI.
Qt recupera automáticamente el bloqueo cuando puede comprobar que murió su dueño.
No borrar manualmente archivos de bloqueo ni ofrecer forzar una instancia activa.

Si está ocupado, avisar «Nimbo ya está abierto» y salir sin abrir/migrar la base.
Si hay un error de permisos/ruta/creación, informar y salir: nunca abrir sin bloqueo.
Usar el mismo guard para el smoke-test temporal, sin acceder a datos personales.
`--version` no necesita bloqueo ni base. No cambia el esquema SQLite.

## Límites

Es una protección cooperativa de los lanzadores actuales de Nimbo con datos locales.
No bloquea editores SQLite externos ni versiones anteriores que no la implementen.
Conservar las transacciones de inventario y ventas. No es un mecanismo multiusuario
para carpetas de red ni contenedores con vistas distintas de procesos/archivos.

## Pruebas

Dos lanzamientos simultáneos: uno obtiene acceso. Rutas relativas/enlaces apuntan
al mismo bloqueo. Bases distintas son independientes. Un archivo antiguo de proceso
vivo no se elimina. Un proceso muerto permite reabrir. Error al abrir o construir UI
libera el bloqueo, y una segunda apertura no crea respaldos ni toca SQLite.

Referencia técnica: https://doc.qt.io/qt-6/qlockfile.html
