# Primera entrega: catálogo de productos y servicios

Fecha: 17 de octubre de 2026
Estado: aprobado por el usuario; primera entrega implementada en la rama codex/catalogo.

Para tener en eunta a futuro "Quisiera agregar algo más para agregar una venta no quisiera agregarla simplemente a una tabla sino que digamos fuese un segundo clic en el primer clic pues mostrará como un resumen de las acciones a realizar y yo le diera nueva venta por ejemplo y ahí se me empezara una nueva interfaz con lo más sencillo de las preguntas de venta, como con un botón agregar la fecha y que esa fecha pues estuviese ya la fecha del día donde estoy por agregar esos datos pero de la forma más minimalista posible. "
 

## Propósito y alcance

Aplicación personal de escritorio para Linux, en español, que sustituirá progresivamente una plantilla Excel para un negocio de impresión 3D con unas 5–10 ventas al mes. Esta entrega permite administrar el catálogo y conservarlo localmente. El usuario solicita una interfaz moderna y sencilla.

Incluye ventana principal, SQLite, alta, edición, búsqueda, filtros y activación/desactivación de productos y servicios. Las cantidades físicas llegarán con el módulo de inventario: activo significa que se ofrece el producto, no que haya existencias.

## Interfaz propuesta

Ventana redimensionable, tamaño inicial aproximado de 1100 × 720 y mínimo de 800 × 560. Tema claro con fondo gris suave, superficies blancas, texto oscuro y acento azul. Tipografía del sistema, espaciado generoso, bordes discretos y estados de foco visibles. El color no será el único indicador de estado.

Barra lateral compacta con nombre provisional «Mi negocio», tambien el logo de la empresa y sección «Catálogo». El área principal contiene título, explicación breve, botón primario «Nuevo», buscador por código o nombre y filtros de tipo y estado. No se mostrarán módulos futuros como botones que no funcionan.
   
Tabla con columnas Código, Nombre, Tipo, Precio de venta y Estado. Precios alineados a la derecha, expresados en COP con formato colombiano. Selección de una fila habilita «Editar» y «Desactivar» o «Activar». Doble clic abre la edición. Los inactivos conservan un distintivo textual.

Sin registros, se muestra «Agrega tu primer producto o servicio» con acceso al formulario. Si una búsqueda no encuentra resultados, se ofrece limpiar los filtros.

El formulario modal contiene código, nombre, tipo (Producto/Servicio), precio en COP y estado activo. Sus botones son «Guardar» y «Cancelar». Los errores se presentan junto al campo pertinente; al guardar se actualiza la tabla conservando filtros y selección cuando sea posible. Si el registro deja de coincidir con los filtros, se informa que se guardó correctamente.

Navegación con teclado y orden de tabulación lógico. Desactivar requiere confirmación y es reversible. No hay borrado definitivo en esta entrega.

## Reglas de datos

- Identificador interno numérico independiente del código comercial. 001, 002, 010, 100,300
- Código obligatorio, almacenado como texto y único. Se conservan letras, guiones y ceros iniciales; no se generan ni renumeran códigos automáticamente. Se rechazan espacios al principio o al final con un mensaje, sin modificarlos silenciosamente. La comparación de duplicados será exacta, distinguiendo mayúsculas y minúsculas.
- Nombre obligatorio, sin aceptar un nombre compuesto únicamente por espacios.
- Tipo limitado a producto o servicio. con mayor enfacis en productos.
- Precio obligatorio, mayor o igual a cero, con hasta dos decimales; se permiten productos gratuitos. Se almacenan centavos de COP como entero y se calculan conversiones con Decimal, sin flotantes para dinero.
- Estado activo/inactivo y fechas de creación y modificación.
  
- Editar el código es una acción explícita del usuario; el identificador interno permanece estable. La interfaz nunca lo sustituye por uno generado.

## Arquitectura

Python, PySide6 con Qt Widgets y sqlite3 de la biblioteca estándar. Sin servidor. Separación entre interfaz, validación del catálogo y repositorio SQLite, con consultas parametrizadas, transacciones y restricción UNIQUE para códigos.

Tabla products: id, code, name, kind, price_cop_cents, active, created_at, updated_at. Se registra la versión del esquema mediante PRAGMA user_version para futuras migraciones. Se validan también en la base de datos tipo, precio no negativo y estado.

La base de datos se ubica en el directorio persistente de datos del usuario obtenido mediante QStandardPaths, fuera del código fuente y del futuro AppImage. El arranque crea el directorio y esquema si no existen, sin reemplazar una base existente. No se incluyen datos ficticios en la base real.

Un fallo de apertura o escritura muestra un mensaje comprensible y no anuncia éxito. Cancelar un formulario no modifica datos. Las operaciones son atómicas.

## Comprobación de la entrega

1. Crear producto con código 010 y verificar que persiste exactamente tras cerrar y reabrir.
2. Crear servicio y un registro de precio cero.
3. Rechazar duplicados, campos obligatorios vacíos y precios inválidos, sin escrituras parciales.
4. Editar, buscar por código y nombre, y combinar filtros de tipo y estado.
5. Desactivar y reactivar sin perder información.
6. Verificar importes decimales exactos y persistencia fuera del directorio de instalación.
7. Revisar visualmente ventana, formulario, tabla vacía, mensajes, teclado y tamaño mínimo.

Se probarán las reglas y la persistencia en una base temporal, y se hará una prueba de arranque Qt en el entorno disponible. Las limitaciones de verificación visual, si las hubiera, se comunicarán.

## Control de versiones

Git local para código, pruebas y documentación, con commits por cambios coherentes verificados. Se excluyen entornos virtuales, bases reales, comprobantes, cachés y ejecutables generados. El usuario ya autorizó usar Git. Las copias de seguridad de información comercial son independientes de Git.

## Requisitos conservados para siguientes entregas

- Configuración del negocio desde la interfaz: editar su nombre y seleccionar, cambiar o quitar el logo, con persistencia entre aperturas. El usuario solicitó conservar el estilo visual actual.
- Prueba temprana de AppImage, con datos persistentes externos al ejecutable.
- Compras con costos discriminados y cotización del dólar por evento de compra y pago de impuestos; informes en COP.
- Inventario por unidad sin alterar códigos comerciales, recepción y etiquetas según el esquema existente.
- Ventas y referencia de factura electrónica externa; efectivo, transferencia, tarjeta y Addi; cuenta y fecha real de recepción, pendientes y comisiones.
- Cobros: en la primera versión cada venta se cobra completa en una sola operación, aunque el dinero se reciba días después. Mantener separadas la fecha de venta y la fecha real de recepción. Para futuras versiones: anticipos y abonos parciales, con varios cobros asociados a una venta e importe pendiente calculado a partir de ellos. Decisión del usuario registrada el 18 de octubre de 2026; todavía no implementada.
- Envío asociado a la venta, con costo y cobro al cliente separados, sin duplicar el gasto mensual.
- Gastos, cuentas, transferencias, gráficos y PDF que respete filtros de cuenta, fechas y tipo de movimiento.
- Importación de Excel, copias de seguridad y restauración de datos y comprobantes.
- Importar y exportar la lista del catálogo en futuras versiones: código, nombre, tipo, marca/proveedor, subtipo, precio de venta recomendado y estado. Conservar los códigos como texto, incluidos sus ceros iniciales. Formatos propuestos para definir al desarrollar: Excel (.xlsx) y CSV. La importación deberá mostrar una vista previa, validar datos y permitir resolver códigos duplicados antes de guardar; la exportación deberá permitir elegir el catálogo completo o los resultados filtrados. Antes de ejecutar una importación o exportación, mostrar un mensaje de confirmación con las opciones Continuar y Cancelar; en la importación, confirmar después de revisar la vista previa y antes de modificar el catálogo (solicitud del 27 de octubre de 2026). Requisito registrado el 17 de octubre de 2026; todavía no implementado.

## Supuestos de esta primera entrega

Tema claro y nombre provisional «Mi negocio» y su logo. Se usa una sola persona y una sola moneda de catálogo (COP). No se conecta la plataforma de facturación: los códigos se introducen manualmente por ahora. Estas decisiones pueden ajustarse en la revisión.

## Ajuste de claridad del catálogo

Se explicita «Catálogo de productos» con descripción de productos y servicios y acción «Agregar al catálogo». Se indica que seleccionar una fila permite editar o desactivar. Se mantiene la desactivación reversible; no se añade borrado definitivo sin definir primero el tratamiento de futuras compras y ventas vinculadas.

## Ancho inicial actualizado

Tras añadir marca y subtipo, el usuario solicita una ventana inicialmente más ancha según su captura de referencia. El tamaño inicial pasa de 1100 × 720 a 1320 × 720 unidades lógicas de Qt, conservando el mínimo redimensionable de 800 × 560.
