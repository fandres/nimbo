# Compras · primera entrega de desarrollo

Validación realizada el 20 de octubre de 2026. Implementa el diseño aprobado en
`docs/superpowers/specs/2026-10-20-compras-design.md`.

## Resultado

- Suite local Linux: 164 pruebas aprobadas.
- Suite en Debian 13 aislado, Python 3.13: 164 pruebas aprobadas.
- Suite con Python/Qt Windows bajo Wine: 164 pruebas aprobadas. No sustituye una
  prueba visual nativa en Windows 11.
- Bases de datos temporales; no se abrió ni migró la base personal para las pruebas.
- Migración 8→9 con respaldo previo, reapertura sin repetir migración y rollback
  comprobado ante fallo inyectado. Persistencia de importes, tasas y fechas después
  de cerrar/reabrir comprobada.
- Cálculos COP/USD, estados provisionales, revisiones, anulación, conflictos,
  idempotencia y rollback de escrituras cubiertos por pruebas.
- Formulario revisado en 1440×900 y 1280×720: sin scroll del cuerpo. En 800×560
  mantiene accesibles los datos mediante scroll de respaldo y el pie fijo.
- Capturas generadas e inspeccionadas a escala 100 % y 150 %, con datos ficticios.
  Captura de referencia: `docs/capturas/compras.png`.

## Ejecución y decisiones registradas

Se continuó en la carpeta y rama actuales siguiendo la preferencia explícita del
usuario. Las tres primeras tareas quedaron guardadas en 2067417, dc6f734 y 0dc4ff3;
la integración de navegación y la verificación final se guardan en los commits
posteriores de esta entrega.

Los editores de líneas y cargos aplican sus datos al formulario, sin escribir en
SQLite. El único Guardar compra persiste el pedido completo. Se separó el editor de
línea en `purchase_line_editor.py` para mantener responsabilidades acotadas y evitar
sobrecargar el formulario. Esta distribución conserva los tres bloques aprobados.

La revisión independiente detectó que Enter podía cancelar el editor de línea/costo.
Se reprodujo con prueba fallida y se corrigió marcando Aplicar como botón predeterminado;
la prueba pasó. La revisión independiente quedó parcial al agotarse la capacidad del
agente revisor; el resto se inspeccionó directamente por el implementador. No se afirma
una revisión externa integral.

La revisión propia encontró una lectura de catálogo innecesaria al aplicar una línea:
un bloqueo podía interrumpir la vista previa. Prueba fallida y corrección comprobada:
se muestran los nombres ya cargados; el repositorio valida de nuevo al guardar.
También se redujo el texto de la acción en Inicio para conservar el ajuste vertical
con tres ventas recientes, verificado por la prueba existente.

## Límites de esta entrega

No registra pagos de compras, existencias, recepciones, costo final por unidad ni
margen. No convierte pedidos en inventario ni modifica ventas existentes. Una tasa
registrada es la ingresada por el usuario, no una TRM consultada automáticamente.

Se conserva alpha.1 como identificación de los paquetes ya entregados, sin
reconstruirlos ni reemplazarlos. Esta función se prueba mediante `./abrir.sh` y usa
esquema 9; los binarios alpha.1 con esquema 8 no abren una base ya migrada. El siguiente
empaquetado deberá recibir una nueva versión, después de revisión funcional.

## Ampliación: gastos por modelo y seguimiento — 2026-10-20

Implementado el plan `docs/superpowers/plans/2026-10-20-costos-por-modelo.md`.

- Esquema 10: cuatro asignaciones COP por línea y seguimiento por concepto nullable.
  Prueba desde una base esquema 9 con payload antiguo: migración, respaldo,
  conservación de totales e idempotencia confirmados.
- Pedidos agrupados, modelos expandidos, costos unitarios, conceptos pendientes,
  filtro de nacionalización y contador de pedidos pendientes de la vista.
- Reparto manual, validación por categoría, costos provisionales y redondeo indicado.
- Historial conserva y presenta las asignaciones y el seguimiento; el estado
  histórico no se convierte en conceptos inventados.
- Pruebas locales finales: 173 PASS. Debian 13: 171 PASS. Python/Qt Windows bajo
  Wine: 171 PASS (antes de las dos pruebas finales de historial/bloqueo; mismo
  comportamiento de producto revisado). Wine no sustituye la prueba en Windows 11.
- Revisión independiente: tres hallazgos corregidos (historial, texto truncado,
  desactivación de seguimiento); segunda revisión sin hallazgos importantes y
  cuatro pruebas específicas PASS.
- Capturas sintéticas a 100 % y 150 %: cuerpo sin desplazamiento en 1440×900 y
  1280×720; en 800×560 desplazamiento vertical de respaldo, botones accesibles.
  `docs/capturas/compras-por-modelo.png` muestra el listado con datos ficticios.
- Decisión de implementación: dos pestañas dentro de Costos adicionales separan
  cargos de seguimiento/asignación y evitan aumentar la altura del formulario.
  Un delegado de Qt ajusta alturas para mostrar nombres largos completos.
- Los paquetes alpha.1 permanecen sin reconstruir; no abren el nuevo esquema.
  Para probar estos cambios, reiniciar desde `./abrir.sh`.

## Ajuste de acceso rápido — 2026-10-21

Estados Pendiente/Registrado/No aplica junto a cada concepto, sin pestaña adicional.
Las categorías sin cargos siguen visibles; varios cargos de la misma categoría
comparten un estado y conservan edición individual. El reparto manual y las
validaciones monetarias se mantienen. Resumen compacto de asignado/por asignar;
el detalle por categoría se consulta en su tooltip.

Filtro de mes y año, alternativo al rango personalizado. Todos los meses conserva
la consulta sin restricción de mes/año. Cabecera del pedido con mes/año destacados
textualmente y fecha exacta debajo. Sin cambios de esquema.

177 pruebas locales PASS. Revisión visual a 1280×720: cuatro conceptos visibles y
sin desplazamiento del cuerpo; 1440×900 también sin desplazamiento. Pantallas
pequeñas conservan desplazamiento de respaldo. Esta iteración no se volvió a
validar en Debian/Wine ni se reconstruyeron paquetes.

Requisito para primera beta anotado en `docs/releases/primera-beta.md`: impedir
instancias simultáneas sobre la misma base. Aún no implementado.

## Filtro mensual de ventas — 2026-10-21

Ventas incorpora mes/año, con rango personalizado alternativo, igual que Compras.
La selección Todos los meses elimina la restricción mensual; el año se usa al
seleccionar un mes. El acceso a cobros pendientes limpia el filtro mensual para
mostrar todos los pendientes. Prueba específica de febrero bisiesto, cambio a
rango personalizado y limpieza de filtros.

La restricción por existencias queda documentada en
`docs/superpowers/specs/2026-10-21-inventario-requisitos.md`; todavía no se aplica
porque el módulo de recepción/inventario aún está pendiente.

## Inversión total en compras — 2026-10-21

Tarjeta global con mercancía y cargos registrados de todos los pedidos vigentes,
independiente de filtros y excluyendo anulados. Identifica costos por completar
como provisionales y aclara que no es saldo disponible ni confirmación de pagos.
179 pruebas locales PASS, incluida conservación del total al cambiar mes y buscar
sin resultados. No se modificaron datos ni esquema de SQLite.

## Filtros estables de Ventas — 2026-10-21

Selector no editable de año actual y cinco anteriores; «Más años anteriores…»
añade bloques de cinco sin cambiar la selección. Fechas Desde/Hasta siempre
visibles, habilitadas al activar rango personalizado. Retención en fila propia,
sin desplazarse al cambiar modo. Controles agrupados en bloque «Filtros».
180 pruebas locales PASS; captura revisada a 1440×900. Recepción aprobada a nivel
de diseño; plan preparado, todavía sin implementación.

## Recepción completa — 2026-10-21

Implementación del plan `docs/superpowers/plans/2026-10-21-recepcion-compras.md`:
recepción atómica por pedido, aviso no bloqueante, filtro y fecha de recepción,
protección de identidad/cantidades y reversión con motivo e historial. Los costos
siguen editables. La inversión registrada no se altera al recibir.

- Esquema 11 con respaldo y migración desde 10 sin generar entradas históricas.
- 189 pruebas PASS en Linux local (7,06 s), Debian 13 (8,25 s) y Python/Qt Windows
  bajo Wine (14,44 s). Incluyen dos conexiones simultáneas, idempotencia, revisión
  obsoleta, rollback, reversión y nueva recepción, guardas y selección de fila hija.
- Revisión independiente: un hallazgo de error de lectura de historial no manejado,
  corregido y cubierto con prueba que falló antes de la corrección y pasó después.
- Capturas con datos ficticios revisadas: confirmación compacta 800×580 y listado
  1440×900. Ningún dato personal utilizado. Windows 11 real sigue pendiente.
- Decisión: receipt_lines conserva código/nombre/cantidad; su vínculo a una línea
  eliminada después de revertir pasa a NULL (ON DELETE SET NULL). Así una corrección
  posterior no elimina la historia ni queda bloqueada por una recepción revertida.
- Límite deliberado: entradas todavía no descontadas por ventas; no anunciar stock
  disponible como si existiera esa integración. Próximo paso: inventario/ventas.
- AppImage/Windows alpha.1 no reconstruidos y no compatibles con esquema 11.

## Separación visual de filtros — 2026-10-21

Subgrupos con título, fondo y borde dentro del bloque Filtros. Ventas separa
Información, Fecha y Retención; Compras separa Información del pedido, Fecha y
Estado de costos/recepción. Fechas siempre visibles y año desplegable también
en Compras. Semántica de filtros conservada. 189 pruebas locales PASS y capturas
revisadas a 1440×900 en ambas pantallas. Sin cambios de base de datos.

## Vista compacta de Ventas — 2026-10-21

Sustituye los bloques verticales por barra principal (búsqueda, estado, cuenta,
fecha y Más filtros). Fecha y opciones adicionales se editan en paneles emergentes
que no desplazan la tabla. Se conservan año desplegable, meses y rango Desde/Hasta.
Etiquetas removibles reflejan filtros activos; Todas no añade una restricción ni
una etiqueta redundante. Más filtros cuenta vigencia, retención e importe.

Resumen Total vendido / Recibido / Por cobrar: suma importes brutos de ventas
vigentes de la vista filtrada; excluye anuladas e incluye envío cobrado. No es
saldo bancario ni utilidad; tooltip aclara que no descuenta comisiones/costos.
Filtro adicional por total mínimo/máximo COP, inclusivo y validado. Estados de
cobro diferenciados por color. Se mantiene acceso a detalle/cobro.

191 pruebas locales PASS, incluyendo suma sin anulados, filtro por importe,
etiquetas removibles y geometría estable al abrir Más filtros. Capturas con datos
ficticios revisadas a 1440×900. No cambia SQLite ni los paquetes; este cambio visual
se aplica a Ventas. No se volvió a ejecutar la suite de Debian/Wine en esta iteración.

### 2026-10-22 · Vista compacta de compras

- Inversión global arriba (pedidos vigentes sin filtros) y total filtrado al pie.
- Barra compacta con búsqueda, vigencia, mes actual predeterminado y paneles de fecha/más filtros que no desplazan la tabla.
- Atajos de costos pendientes y recepción: respetan fecha y búsqueda, cuentan pedidos vigentes y sustituyen los filtros de estado para evitar combinaciones contradictorias.
- Pedidos desplegables con proveedor, mes, fecha exacta, modelos y costos unitarios. Estados separados por colores, total en columna propia y botones Ver / editar y Recibir por pedido.
- Referencia disponible al pasar el cursor sobre el encabezado del pedido y en el formulario.
- Validación: 194 pruebas correctas con Qt offscreen; capturas con datos sintéticos a 1440×900 y 1920×1080. Captura guardada en docs/capturas/compras-compactas.png.
- Cambios en el código fuente; no se reconstruyeron los paquetes AppImage/Windows.

### 2026-10-22 · Selección de pedidos

- Colores de selección explícitos: fondo azul suave y texto oscuro para conservar los importes visibles con temas Linux que usan texto seleccionado blanco.
- Un clic en el encabezado o en un producto resalta el pedido y todas sus líneas; cambiar de pedido retira el resaltado anterior.
- El delegado no vuelve a dibujar el texto debajo de los encabezados y etiquetas que ya tienen widgets.
- Validación: prueba de clics y contraste con paleta blanca, inspección visual con datos sintéticos y 195 pruebas correctas.

### 2026-10-22 · Resumen mensual opcional

- Configuración → Visualización → Mostrar el total comprado en el mes actual, desactivado por defecto.
- Muestra un importe junto a la inversión global: pedidos vigentes cuya fecha de compra pertenece al mes actual, con mercancía y gastos registrados, incluidos costos provisionales. No cambia con los filtros del listado ni representa pagos.
- Preferencia visual local persistida mediante QSettings (Nimbo/Nimbo), sin modificar el esquema contable. Cambia de inmediato al activar o desactivar la casilla.
- Validación: persistencia en archivo temporal, estado predeterminado, exclusión de anulaciones y otros meses, independencia de filtros, inspección visual a 1440×900 y 196 pruebas correctas.

### 2026-10-22 · Año actual predeterminado

- Compras abre con «Todo el año» y el año actual, filtrando del 1 de enero al 31 de diciembre.
- Conserva meses individuales y rango personalizado; «Todos los años» permite consultar el historial completo.
- El total filtrado y los atajos respetan el período. La inversión global y el resumen mensual opcional mantienen sus respectivos alcances.
- Validación: 197 pruebas correctas, incluida exclusión del año anterior, consulta histórica y rango entre años.
