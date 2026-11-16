# Alfa 0.2 · 0.2.0-alpha.1

## Nueva venta · 22 de octubre de 2026

Rediseño basado en la propuesta del usuario:

- Cliente y fecha a la izquierda; cédula/NIT y correo desplegables.
- Búsqueda de catálogo con autocompletado y Enter para agregar una vez; nunca guarda la venta con Enter desde el buscador.
- Cantidad y precio editables por fila, total actualizado y acción Quitar por producto.
- Pago y resumen a la derecha. Efectivo, transferencia, tarjeta y Otro para plataformas adicionales. Se conservan cuentas, fecha de recepción y comisión real.
- Resumen con total al cliente, comisión y envío, neto conocido y desglose expandible. El neto no es utilidad; la retención del 2,5 % sigue siendo informativa.
- Factura y envío desplegables; transportadora, destino, guía y pago del envío en un desplegable adicional. Cerrarlos no borra datos.
- Guardar y Cancelar se trasladan al pie en ventanas pequeñas para mantenerlos accesibles.
- Configuración → Ventas: exigir cédula o NIT al cliente de nuevas ventas. Desactivado por defecto; si se activa, el documento queda visible y se valida al guardar. Correo opcional y ventas previas intactas. Preferencia local de este equipo, guardada con QSettings.

## Verificación

202 pruebas correctas con Qt offscreen tanto en Debian 13 como en Python de Windows bajo Wine. Arranque del AppImage en Debian 13 sin Python y del ZIP extraído en un prefijo Wine sin Python: correctos. Nuevas pruebas cubren Enter/autocompletado sin duplicación, edición y eliminación de líneas, precios inválidos sin recuperar silenciosamente valores antiguos, datos opcionales conservados y documento obligatorio configurable/persistente. Inspección visual con datos sintéticos a 1440×900; captura en `docs/capturas/nueva-venta-redisenada.png`.

## Distribución

Código propio bajo MIT; avisos de Qt/PySide6 bajo LGPLv3 y licencias de terceros incluidos.
Paquetes x86_64: AppImage construido sobre Debian 13 y portable Windows construido
con Python 3.13/PyInstaller para Windows bajo Wine. El ZIP se extrae completo.
Se entrega además un archivo de fuentes con instrucciones y sumas SHA-256.

Los complementos Qt PDF y Virtual Keyboard no se usan ni se distribuyen. Las
bibliotecas compartidas pueden sustituirse; consulta REEMPLAZAR-BIBLIOTECAS.txt.

La prueba visual final en Debian 13 y Windows 11 corresponde a equipos reales.
No se garantiza Debian 12 ni distribuciones con glibc anterior a Debian 13.
El control de disponibilidad de inventario descontando ventas sigue pendiente.
