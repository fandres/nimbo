# Alfa 0.4 · 0.4.0-alpha.1

Entrega preparada el 3 y 4 de noviembre de 2026 para Debian 13 y Windows 11, Intel/AMD x86-64.

## Cambios desde alfa 0.3

- IVA opcional en ventas y compras, con opciones de importe incluido o separado.
- Comisiones configurables por plataforma y tramos de importe; consulta de gastos por plataforma.
- Retenciones descontadas del depósito para las nuevas ventas, con cuenta auxiliar y requisitos de factura/correo configurables. Las ventas históricas conservan su política.
- Alias, detalles y celular opcionales del cliente; mejoras de filtros y actualización de cuentas.
- Configuración para editar, anular y eliminar ventas. Eliminar está apagado por defecto, requiere advertencia al habilitarlo y confirmación por venta.
- Corrección de productos, cantidades y precios de ventas guardadas con historial y actualización atómica de existencias y totales.
- Informes PDF y mejoras de formularios incorporadas desde la entrega anterior.

## Datos y actualización

Se conserva la ubicación de datos Fandres/MiNegocio. Esquema SQLite 24; la migración genera un respaldo previo de SQLite. Antes de actualizar, cerrar Nimbo y respaldar toda su carpeta de datos, incluida Documentos. No abrir una versión antigua sobre la base ya migrada.

Los paquetes no incluyen bases de datos comerciales. La eliminación no borra las copias físicas de adjuntos ni el registro de movimientos de inventario. No modifica facturas en plataformas externas.

## Construcción

Se reutilizan las recetas y herramientas de la alfa 0.3: Python 3.13.5, PySide6 6.12.0 y PyInstaller 6.22.3. Linux se construye en Debian 13 aislado; Windows con Python y PyInstaller de Windows bajo Wine. No se declara validación en un escritorio Windows 11 real ni compatibilidad con Debian 12.

Los paquetes incluyen licencia MIT y avisos de terceros; las fuentes correspondientes se entregan en Nimbo-0.4.0-alpha.1-sources.zip. Los manifiestos JSON y archivos SHA-256 acompañan cada binario.

## Verificación de la entrega

- 398 pruebas aprobadas en Debian 13 (Python 3.13.5).
- 398 pruebas aprobadas con Python/Qt de Windows bajo Wine 11.21.
- El complemento offscreen de Qt en Wine necesitó QT_QPA_FONTDIR apuntando a
  fuentes locales del entorno de pruebas. Sin ello dibujaba cuadrados y producía
  dos falsos fallos de tamaño. No se modificó el diseño ni se incorporaron fuentes
  adicionales a los paquetes.
- AppImage: arranque correcto del binario y del paquete; arranque y versión
  comprobados en Debian 13 aislado sin Python. Versión: 0.4.0-alpha.1.
- Windows: ZIP íntegro, sin SQLite comerciales; ejecutable extraído arrancado
  correctamente en un prefijo Wine sin Python con SQLite temporal.
- SHA-256 de ambos binarios verificado. Bibliotecas Debian iguales a la alfa 0.3;
  se conservan las fuentes correspondientes y se actualiza el código de Nimbo.
- Pruebas de escritorio y uso real de esta entrega en Debian 13 y Windows 11:
  pendientes del usuario. No equivale a una validación nativa de Windows 11.

Archivos:
- Nimbo-0.4.0-alpha.1-linux-x86_64.AppImage
- Nimbo-0.4.0-alpha.1-windows-x86_64.zip
- Nimbo-0.4.0-alpha.1-sources.zip
