# Verificación del módulo de ventas

18 de octubre de 2026. Implementación en `codex/catalogo`.

## Resultado

`QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`: **92 pruebas aprobadas**, incluidas las del catálogo existente. `git diff --check` sin errores.

Se verificaron los cálculos de Bolt (3,59 % + $900) y Addi (7,735 %), envío cobrado dentro de la comisión, envío gratuito, redondeo, límites monetarios, instantáneas históricas, cobro único y pago de envío independiente. Las tarifas son las suministradas por el usuario.

Persistencia: migración v1/v2→v3 con respaldo, fallo de backup, reversión de migración interrumpida, error entre líneas sin venta parcial, cambios de tarifas, dos conexiones intentando cobrar la misma venta, reintento de guardado y referencias de productos tras edición.

Interfaz: selección de adicionales y limpieza al ocultarlas, venta/cobro/envío, edición de tarifas, error visible desde Inicio, datos conservados tras fallo al guardar y protección frente a guardado repetido. Inicio cabe a 1320 × 720 incluso con tres ventas recientes; venta rápida con envío pagado cabe a 1060 × 690. A 800 × 560 mantiene Guardar accesible y evita desplazamiento horizontal.

## Revisión independiente

Una revisión de código encontró dos problemas: búsqueda editable que podía conservar un producto anterior y error de apertura oculto al iniciar una venta desde Inicio. Ambos se reprodujeron, corrigieron y quedaron cubiertos por pruebas. También se corrigió el exceso de altura del formulario y del Inicio con ventas reales.

## Evidencia visual

Capturas generadas con una base temporal, sin datos personales:
- `capturas/venta-rapida.png`
- `capturas/detalle-venta.png`
- `capturas/ventas.png`
- `capturas/configuracion-pagos.png`
- `capturas/inicio-ventas.png`

Se revisaron visualmente venta rápida, detalle, configuración e Inicio mediante renderizado Qt offscreen. No se realizó una sesión manual automatizada sobre el escritorio nativo ni se abrió/migró la base personal durante el desarrollo. La migración real se ejecutará al abrir la aplicación nueva.

## Límites de esta entrega

No hay abonos, pagos mixtos, devoluciones ni edición monetaria/anulación de ventas guardadas. La referencia de factura sí puede corregirse. Compras, costos de mercancía, inventario físico, saldos completos, gastos generales, informes y PDF siguen pendientes. El neto mostrado no es rentabilidad.

## Ajustes del plan

Los detalles y resúmenes de persistencia se exponen como diccionarios con campos explícitos; entradas y cálculos conservan dataclasses. Las pruebas de cuentas se agruparon en `test_database.py`. La configuración se conserva en la misma conexión, y sus errores no borran formularios. Se mantuvieron las decisiones de trabajar en la carpeta y rama actuales.

## Reorganización visual del formulario

A solicitud del usuario, la venta rápida se divide en tres tarjetas numeradas: Qué vendemos, Cómo me pagaron y Envío y factura. Se conserva el buscador y se diferencia Agregar (azul suave), Quitar (rojo tenue al seleccionar una línea) y Guardar (azul principal). Resumen y botones finales fuera del área desplazable. A 1280 × 700 se comprueba el formulario completo con producto, comisión, plataformas adicionales y envío pagado; en ventanas menores las tarjetas pasan a una columna. La captura `venta-rapida.png` muestra el diseño actualizado.

## Cuentas por forma de pago y agrupación del cobro

Se añaden tipos de cuenta (efectivo / banco o billetera), una predeterminada por tipo y política configurable por forma de pago. Efectivo propone la caja predeterminada sin impedir elegir otra cuenta; transferencia solo muestra bancos/billeteras activos. Se conservan los nombres de plataformas aunque se renombren los métodos. Nequi, Bancolombia y Daviplata se registran como cuentas propias desde Configuración; no se crean cuentas ficticias en la base personal.

El esquema 4 migra con respaldo desde versiones anteriores, conserva tarifas y cuentas, clasifica la caja inicial como efectivo y las demás como bancos/billeteras (editable). Venta rápida diferencia cuenta de destino y confirmación del cobro con recuadros y títulos. Fecha de venta arriba, hoy por defecto y calendario editable. Campos de recepción solo cuando se recibe; comisión real visible para métodos con comisión configurada.

Se comprueba venta de efectivo con producto y resumen sin desplazamiento vertical, también con QT_SCALE_FACTOR=1.5. Evidencia: `capturas/venta-efectivo.png`. Se mantiene desplazamiento de respaldo en pantallas pequeñas.

## Cliente, transportadora y marca de retención

- Esquema 5 con respaldo previo, nombres de cliente para ventas nuevas, transportadoras editables, ciudad opcional e instantánea histórica de la transportadora.
- Factura y envío en bloques visuales separados. Cliente visible encima de las secciones. Importes seleccionados completos al primer clic de entrada.
- Retención informativa según decisión explícita del usuario: no cambia total, comisión, depósito ni neto. Filtro combinable con fechas; marca corregible desde detalle de factura. No se registra ni se suma un importe retenido.
- Pruebas: migración desde v4 conservando cuentas personalizadas, cliente obligatorio, persistencia/búsqueda por cliente, transportadora histórica tras renombrar, mantenimiento de importes al marcar retención, filtros por fechas/retención, edición de transportadoras y selección de importe al primer clic.
- Verificación final: **102 pruebas aprobadas** con Qt offscreen; diff sin errores. Captura actualizada `capturas/venta-rapida.png` revisada; prueba de formulario con envío pagado y adicionales sin desplazamiento en tamaño normal. Base personal no utilizada para pruebas.

## Búsqueda al primer clic y cálculo informativo del 2,5 %

El buscador utiliza un placeholder gris real y selección completa al primer clic de entrada; no trata el texto guía como un producto. Se mantiene la validación contra selecciones anteriores mientras se escribe. Factura y envío tienen fondos diferenciados y separación adicional; «(informativo)» usa el estilo gris secundario.

Por confirmación del usuario, se calcula el 2,5 % sobre el total comercial con envío cobrado, sin alterar cobro ni comisiones. Se redondea HALF_UP a centavos, se muestra al marcar retención y también al consultar el detalle. El valor es derivado del total histórico inmutable mediante la función compartida; las consultas de ventas lo exponen como withholding_cents para informes futuros. La tasa es fija en esta entrega, no una regla tributaria inferida.

Comprobaciones: $1.020.000 → $25.500; $2.520.000 → $63.000; depósito intacto. Prueba de búsqueda con primer clic y reemplazo de selección. Prueba de formulario con retención, envío pagado y plataformas adicionales sin desplazamiento en tamaño normal. Resultado: 105 pruebas aprobadas.

## Altura estable al mostrar plataformas adicionales

Las plataformas adicionales se eligen en un desplegable de altura fija al activar el interruptor. Se conserva la exclusión entre elección principal y adicional, y ocultar adicionales limpia la selección. Se compactaron márgenes y el bloque de cobro, sin ocultar contenido ni forzar ScrollBarAlwaysOff.

Prueba con 13 plataformas adicionales, producto, retención, envío pagado y cobro recibido: sin desplazamiento vertical a 1280 × 680. Comprobada también con escalado 150 %. Suite completa: 106 pruebas aprobadas; prueba de selección de la última plataforma adicional incluida. Pantallas estrechas conservan el diseño en una columna con desplazamiento de respaldo.

Git: cambios guardados por conjuntos funcionales en commits locales; no hay remoto configurado al verificar este ajuste.

## Copia del valor de envío y primer clic

El cobro de envío escrito por el usuario se copia al costo mientras ese costo no se haya editado manualmente. Escribir solo el costo mantiene el cobro al cliente en cero; al modificar el costo, los cambios posteriores del cobro ya no lo sobrescriben. La copia usa textEdited, de modo que los cambios automáticos no se confunden con una edición manual.

Se reprodujo el fallo del primer clic cuando Qt asignaba foco antes de procesar la pulsación; se conserva la selección pendiente hasta soltar el botón. Los importes de ventas admiten también miles con puntos en formato colombiano (42.500 o 42.500,50), además del formato sin miles existente.

Verificación: 110 pruebas aprobadas; copia, anulación de copia por edición manual, costo sin cobro, primer clic con foco previo y conversión de importes agrupados cubiertos.

### Guía de envío y resumen visual (18 de octubre de 2026)

- Campo opcional de guía/tracking junto a la ciudad; conserva letras y ceros iniciales.
- Puede completarse o corregirse desde el detalle con «Guardar guía».
- Base actualizada a versión 6 con copia previa; las ventas anteriores quedan sin guía.
- Resumen separado en tres tarjetas: total al cliente, comisión más costo de envío y neto restante. Desglosa envío cobrado y depósito recibido/estimado. El neto no representa utilidad ni descuenta la retención informativa.
- Verificados guardado y edición de guía, migración desde versión 5, cálculos del resumen y ausencia de desplazamiento a 1280×680 con todas las opciones activadas.

### Cliente y fecha destacados (18 de octubre de 2026)

- Primer bloque principal «1 · Cliente y fecha», separado del título, con el cliente identificado como obligatorio.
- Las secciones siguientes se numeran 2, 3 y 4 para expresar el orden de llenado.
- Ventana inicial de 1280×800; verificada sin desplazamiento con envío pagado, retención y plataformas adicionales desplegadas. Se conserva el desplazamiento adaptable en ventanas pequeñas.
- Suite completa: 113 pruebas aprobadas.

### Calendario con un clic (18 de octubre de 2026)

- Clic sobre el texto de cualquier selector de fecha abre el calendario nativo de Qt, sin necesidad de escribir día/mes/año ni apuntar a la flecha.
- Icono de calendario junto a «Fecha de venta»; conserva selección por teclado y límites de fecha existentes.
- Verificados apertura al primer clic, elección de otro día y cierre del calendario. Suite: 114 pruebas aprobadas; 16 pruebas de interfaz también aprobadas con escala 1,5.

### Destino y guía en filas separadas (18 de octubre de 2026)

- Se retira el icono de fecha; se conserva apertura del calendario al hacer clic.
- Destino y guía se muestran uno debajo del otro, ambos opcionales.
- Se compacta el relleno interior de los controles del bloque de envío y se elimina la reserva vacía del mensaje de error. Los errores siguen mostrándose cuando corresponde.
- Verificados 1230×780 con transportadora seleccionada, ciudad y guía, cobro recibido, envío pagado, retención y otras plataformas activadas, sin barra vertical. Suite completa: 114 pruebas; 16 pruebas de interfaz aprobadas también con escala 1,5.

### Datos del cliente, ciudades y pago flexible del envío (19 de octubre de 2026)

- Cédula/NIT y correo opcionales en el primer bloque; se guardan como texto y se consultan en el detalle. El documento conserva ceros iniciales.
- Autocompletado por prefijo de las ciudades de ventas guardadas, sin distinguir mayúsculas. Permite ciudades nuevas y mantiene las sugerencias entre sesiones.
- El envío puede quedar pendiente; se registra después desde el detalle. Si ya se pagó, la cuenta y la forma de pago pueden quedar por completar, con aviso visible.
- Formas del pago del envío: por completar, desde una cuenta, tarjeta débito o tarjeta crédito. Se pueden completar/corregir posteriormente sin cambiar el importe, la fecha ni duplicar el pago.
- Migración a versión 7 con respaldo previo: conserva pagos existentes; los datos nuevos del cliente quedan vacíos en ventas anteriores.
- Verificados guardado sin cuenta, actualización posterior, pago pendiente, tipos de tarjeta, conservación de pagos anteriores, datos del cliente al reabrir y autocompletado «bog» → «Bogotá».
- Pendiente para el módulo de dinero: distinguir cargos a crédito de salidas bancarias, registrar la liquidación posterior de la tarjeta sin duplicar el gasto y tratar explícitamente pagos sin cuenta. Hoy el selector guarda la forma usada y la cuenta asociada; no implementa gestión de deuda ni flujo de caja.

### Detalle con guardado único (19 de octubre de 2026)

- Ventana horizontal de 1280×780, cliente separado y tres bloques: productos/factura, cobro y envío. Importes en las tres tarjetas de colores compartidas con venta rápida.
- Un solo botón principal «Guardar cambios». Las casillas de cobro/envío pendientes deben marcarse expresamente; editar factura, retención o guía no registra pagos por sí solo.
- Guardado atómico: un error en cualquier pago revierte toda la operación. Cobros y fechas de pagos ya registrados se conservan; los datos del pago del envío siguen pudiendo completarse.
- Sin desplazamiento general a 1230×760 con ambos pagos marcados. En ventanas pequeñas se conserva acceso al pie y desplazamiento para no ocultar campos. Listas extensas de productos se desplazan dentro de su propio bloque.
- Retención en la fuente: filtro rotulado junto a las fechas, con Todas/Con retención/Sin retención.
- Validación: 124 pruebas completas; 23 de interfaz/navegación también con escala 1,5.

### Anulación con historial (19 de octubre de 2026)

- «Anular venta» en el detalle pide confirmación y motivo opcional. No borra productos, cobros ni pagos; registra fecha/hora UTC y motivo.
- Ventas muestra Vigentes por defecto y permite filtrar Anuladas o Todas las ventas. Las anuladas aparecen con estado «Anulada» y se consultan sin modificar sus datos.
- Resúmenes de Inicio, pendientes y filtros habituales de retención excluyen anuladas. Para consultar su retención histórica, seleccionar Anuladas o Todas las ventas.
- La anulación es local: no modifica documentos en plataformas externas ni ejecuta devoluciones de dinero.
- Todas las vías de modificación del repositorio rechazan ventas anuladas, incluso si el formulario estaba abierto antes. Repetir la anulación conserva el motivo y fecha originales.
- Migración a versión 8 con respaldo, preservando datos de cliente y formas de pago existentes.
- 128 pruebas aprobadas; 24 de interfaz/navegación también con escala 1,5.
