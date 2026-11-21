# Adjuntos de ventas: completar soporte de XML

El usuario aprobó continuar con adjuntos PDF/XML/imágenes y copias organizadas por año y mes, conservando originales y confirmación para retirar vínculos. No generar otra beta.

La exploración encontró que el listado de ventas y su detalle ya incorporan el botón de clip y el gestor compartido, incluidos apertura, contador, carpetas y confirmación. El cambio necesario es añadir XML al conjunto de formatos admitidos y al selector, sin duplicar la interfaz ni crear otro sistema de almacenamiento. Se reutiliza el gestor en ventas, compras y gastos; no requiere migración de base.

El XML se copia como bytes, sin interpretar su contenido. La importación asistida sigue pendiente. Los adjuntos se agregan a ventas guardadas, usando su fecha e identificador; se mantienen los archivos físicos cuando se retira el vínculo.

Verificación: pruebas de copia XML mayúscula, organización mensual, preservación del original, restauración byte a byte desde respaldo, selector de archivos, apertura, contador y cancelación/confirmación de retirada. Datos de pruebas temporales.
