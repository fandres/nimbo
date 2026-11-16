# Nimbo · mejoras para futuras versiones

## Asistente inicial: modalidad de compras del negocio

Solicitud del usuario: 23 de octubre de 2026. Pendiente; no implementar en la
etapa actual de inventario ni asignar todavía a una versión concreta.

En una ampliación futura del asistente de primera apertura del programa,
preguntar qué modalidad necesita el emprendedor:

- **Compras e importación:** para negocios que necesitan registrar mercancía,
  transporte internacional, nacionalización, impuestos y demás costos asociados.
- **Compras simples, por ejemplo de insumos:** adaptar el módulo de Compras a
  negocios que no necesitan el proceso de importación.

La selección servirá para adecuar el menú y las opciones de Compras a las
necesidades del negocio. Esta pregunta es adicional a la configuración inicial
del inventario; no sustituye la confirmación de existencias actuales por modelo.

Antes de implementarla, definir el alcance exacto de cada modalidad y cómo
permitir cambiarla posteriormente conservando los datos existentes. No hay una
modalidad predeterminada acordada todavía.

## Seguridad: contraseña opcional de acceso

Solicitud del usuario: 25 de octubre de 2026. **Pendiente para la etapa final
del desarrollo; no implementar ahora.**

- Permitir habilitar o deshabilitar la protección del programa con contraseña
  desde Configuración.
- Dejarla **desactivada de forma predeterminada**.
- Al habilitarla, permitir crear y cambiar la contraseña y solicitarla al
  abrir Nimbo.
- Antes de implementarla, definir el cambio/desactivación con verificación de
  la contraseña actual, su almacenamiento seguro y el procedimiento ante olvido.
- Definir por separado si se protegerán también los archivos y las copias de
  seguridad: una clave de acceso a la interfaz no cifra por sí sola esos datos.

## Costos adicionales propios de cada emprendimiento

- En una versión futura, iniciar la configuración de costos adicionales de compras
  sin conceptos predefinidos de importación. Cada emprendedor creará sus propios
  costos según su actividad (o elegirá una plantilla opcional en el asistente).
- Aplicar esta limpieza únicamente a instalaciones nuevas: conservar conceptos,
  importes y seguimiento de los pedidos existentes. No borrar datos históricos.
- Por ahora se mantienen los conceptos actuales, administrables desde Configuración.

## Beta 2
- Revisar los colores de los botones de toda la aplicación: coherencia entre acciones, diferenciación de compras y ventas, contraste y estados de interacción.

## Importación asistida de facturas electrónicas
Solicitud: 2 de noviembre de 2026. Pendiente.
- Permitir cargar el XML de la factura para proponer cliente/proveedor, identificación, factura, fecha, productos, cantidades, precios e impuestos.
- Mostrar una previsualización editable antes de registrar la operación; no guardar automáticamente ni asumir que una factura ya está pagada.
- Resolver la correspondencia con los códigos existentes del catálogo y detectar facturas duplicadas.
- Conservar una copia del documento como adjunto.
- Evaluar después extracción de PDF e imágenes mediante OCR, indicando datos incompletos o inciertos.
- Validar los formatos admitidos con muestras de facturas antes de implementar.

## Método de valoración del inventario configurable

Solicitud del usuario: 6 de noviembre de 2026.

- Primera implementación de costo de ventas: FIFO automático, sin elección manual
  del pedido en la venta. Consumir primero las unidades recibidas más antiguas.
- En una versión posterior, permitir elegir desde Configuración el método de
  valoración. Definir los métodos admitidos y cómo efectuar el cambio conservando
  trazabilidad; no recalcular ni alterar silenciosamente ventas anteriores.
- No añadir el selector en esta primera entrega.
