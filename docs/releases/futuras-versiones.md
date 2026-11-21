# Nimbo · mejoras para futuras versiones

## Arquitectura de módulos opcionales

Acuerdo del usuario: 18 de noviembre de 2026. **Desarrollo futuro, sin versión
asignada. Tener presente esta dirección al diseñar nuevas funcionalidades.**

- Comenzar con módulos integrados que se puedan activar desde
  **Configuración → Módulos**. Cada emprendedor habilitará los que necesite.
- Mantener separados el código, los datos específicos y las migraciones de cada
  módulo. Esto no exige una base de datos distinta por módulo.
- Definir interfaces de acceso a compras, ventas, catálogo, adjuntos e informes,
  evitando que los módulos opcionales dependan de detalles internos de sus pantallas.
- Prever un registro común de módulos con identificador estable, versión,
  dependencias y puntos de integración en navegación y Configuración.
- Activar o desactivar un módulo debe controlar sus accesos y acciones. Desactivarlo
  no debe borrar datos, adjuntos ni historial, ni impedir usar las funciones básicas.
- Los respaldos deben incluir también los datos de módulos desactivados. Definir
  validaciones de compatibilidad y dependencias antes de habilitar o actualizar.
- Preparar esta separación para incorporar otros módulos futuros sin reestructurar
  toda la aplicación. No asumir que las funciones actuales ya son plugins independientes.
- Los plugins descargables o de terceros quedan como una etapa posterior: requerirán
  contratos de compatibilidad, instalación, permisos y actualizaciones propios.
  No implementar ahora un cargador de plugins ni un catálogo de extensiones.

Antes de construir la infraestructura, concretar sus contratos y ciclo de vida
mediante un diseño técnico y pruebas de activación, desactivación y restauración.
Por ahora se documenta la dirección; no se realiza una refactorización general.

## Garantías: futuro módulo opcional

Solicitud del usuario: 18 de noviembre de 2026. **Aplazado para el final;
no implementar ahora ni asignar a la siguiente beta.**

- Candidato inicial a la arquitectura de módulos opcionales descrita arriba.
- Desactivado de forma predeterminada y activable desde Configuración.
- Seguimiento desde la fecha de compra, con atajos de **3, 6 y 12 meses** y
  un plazo personalizado.
- Propuesta para concretar al retomarlo: vencimiento, tiempo restante, estados
  vigente/próxima a vencer/vencida y búsqueda por producto, proveedor o factura.
- Pendiente aclarar si cubre garantías recibidas del proveedor, garantías ofrecidas
  al cliente o ambas. No asumir resuelta esta distinción.
- Definir también el seguimiento por producto o unidad, las fechas y las reglas
  para compras/ventas corregidas o anuladas antes de implementarlo.

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
- La copia del XML como adjunto ya está disponible desde el 18 de noviembre de 2026; queda pendiente utilizar su contenido para proponer datos.
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

## Tema claro, oscuro y automático

Solicitud del usuario: 18 de noviembre de 2026. **Pendiente para versiones futuras;
no incluir en 0.6.0-beta.2.**

- En Configuración, permitir elegir **Claro**, **Oscuro** o **Según el sistema**.
- Guardar la preferencia y, en modo automático, seguir el tema del sistema operativo.
- Centralizar colores y estilos para que los módulos actuales y futuros respeten
  el tema, incluidos diálogos, tablas, estados, iconos y gráficos.
- Verificar contraste y legibilidad en Debian y Windows. Definir por separado
  el aspecto de impresión/PDF para no trasladar fondos oscuros a los documentos.
