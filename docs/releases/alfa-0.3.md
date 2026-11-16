# Alfa 0.3 · 0.3.0-alpha.1

Entrega Linux Debian 13 x86_64 solicitada el 27 de octubre de 2026. La entrega Windows se preparó el 28 de octubre de 2026.

Cambios desde la alfa 0.2: inventario y recepción, gastos y préstamos, control opcional de tarjetas, resúmenes de ventas, mejoras de filtros y formularios, proveedores con alias, guía opcional de compras, costos configurables y adjuntos locales PDF/PNG/JPG. El selector Total/Por unidad conserva los importes exactos. Tab completa únicamente una coincidencia.

Los adjuntos guardan copias en Documentos por año/mes y tipo de operación junto a SQLite. Respaldo: conservar toda la carpeta de datos, no solo SQLite. Migración de base a versión 19 con respaldo previo de SQLite. La identidad de almacenamiento MiNegocio se conserva.

Pendientes acordados:
- Mejorar ubicación, visibilidad y diseño del clip y de la ventana de documentos.
- Ampliar documentos de ventas para admitir XML de factura electrónica junto al PDF (PDF ya admitido). Conservar las copias sin modificar ni emitir facturas.

Construcción y verificación: usar el entorno Debian 13 existente y la receta packaging/build.py. Registrar los resultados reales tras construir. Prueba visual en el equipo Debian del usuario pendiente; no se anuncia compatibilidad con Debian 12.

## Verificación de la entrega Linux

- 351 pruebas aprobadas en Debian 13 con Python 3.13.5 y Qt offscreen.
- AppImage construida con PyInstaller 6.22.3 y PySide6 6.12.0. Arranque automático del ejecutable y de la AppImage: correctos.
- AppImage arrancada también en el entorno Debian 13 limpio sin Python de las entregas anteriores: salida 0, con base temporal.
- Entorno aislado: bibliotecas Debian 13, kernel compartido con el anfitrión. La comprobación offscreen no reemplaza la prueba visual del escritorio y escala del equipo de ventas.
- Fuentes de terceros reutilizadas de alfa 0.2: mismas versiones; el inventario nuevo no requiere fuentes Debian adicionales. Se incluye el código actualizado de Nimbo.

Archivo: `dist/Nimbo-0.3.0-alpha.1-linux-x86_64.AppImage`, acompañado de manifiesto JSON, SHA-256 y `Nimbo-0.3.0-alpha.1-sources.zip`. La verificación de Windows se describe a continuación.

## Entrega Windows · 28 de octubre de 2026

- Portable x86_64 preparado con Python 3.13.5, PyInstaller 6.22.3 y PySide6 6.12.0 de Windows bajo Wine.
- 351 pruebas aprobadas en Windows/Wine y 351 en Linux anfitrión.
- Ajustes de presentación comprobados con las pruebas existentes: altura de nombres largos de proveedores y márgenes de Nueva venta en ventanas pequeñas.
- La AppImage ya entregada se conserva. Estos ajustes se incluyen en el portable Windows y en el complemento `Nimbo-0.3.0-alpha.1-windows-source.zip`; las fuentes de terceros siguen en el archivo común `Nimbo-0.3.0-alpha.1-sources.zip`.
- Validación visual y funcional en Windows 11 real pendiente del usuario.
- ZIP íntegro y SHA-256 verificado, sin bases comerciales incluidas. Tamaño: 39.405.783 bytes.
- Ejecutable extraído probado con éxito en el prefijo Wine limpio sin Python, tanto con Qt offscreen como con el complemento gráfico Windows. Base de datos temporal en ambas comprobaciones; no se modificaron los datos del negocio.
