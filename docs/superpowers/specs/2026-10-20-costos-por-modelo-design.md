# Compras: resumen por pedido y gastos manuales por modelo

## Objetivo acordado

Identificar las máquinas de cada pedido sin abrir el editor y conocer su costo
unitario con gastos. Los pedidos pueden mezclar modelos: el usuario asignará los
gastos manualmente, porque el peso y volumen no son proporcionales al precio.
Se mantienen los códigos del catálogo y los importes originales COP/USD.

## Listado de compras

Cada pedido tendrá una cabecera con fecha, proveedor, unidades, total registrado y
estado de costos. Debajo se mostrarán, expandidas inicialmente, sus líneas con
código, nombre, cantidad, compra por unidad COP y costo con gastos por unidad COP.
Se podrá contraer un pedido. Seleccionar su cabecera o cualquier línea y pulsar
«Ver / editar compra», o hacer doble clic, abrirá el mismo pedido.

La referencia no ocupará una columna principal. Continuará editable y consultable
como «Factura / pedido · opcional» en el detalle y seguirá incluida en la búsqueda.
La búsqueda por producto mostrará el pedido completo con todas sus líneas. Los
contadores y totales contarán pedidos, nunca las filas hijas. Las compras anuladas
mantendrán su identificación y quedarán excluidas del total vigente.

Se conservarán los filtros actuales. El listado tendrá desplazamiento vertical
cuando haya muchos pedidos, sin imponer desplazamiento horizontal en pantallas
amplias. Los nombres largos podrán ocupar más de una línea.

## Asignación manual

Se conservará la lista actual de cargos del pedido como fuente de los gastos
registrados, con moneda, tasa y fecha propias. El editor de cada línea de producto
incorporará un grupo «Gastos asignados a estas unidades · COP» con cuatro importes:
envío internacional, importación / gestión, impuestos y otros costos.

Cada importe corresponde al conjunto de unidades de esa línea, no a una unidad.
La ayuda mostrará su cantidad y un ejemplo: $120.000 para tres unidades representa
$40.000 por unidad. No habrá reparto automático entre modelos. Tampoco se sumarán
estos importes de nuevo al total del pedido: distribuyen los cargos ya registrados.

Si el mismo modelo aparece en líneas distintas por tener precios diferentes,
seguirán siendo líneas independientes. Cada una conservará sus gastos y costo;
no se mezclarán mediante un promedio entre líneas.

En el formulario principal habrá un resumen de asignación por categoría:
«Registrado», «Asignado» y «Pendiente de asignar». Mostrará también cualquier
exceso durante la edición. Se admitirá guardar asignaciones parciales, pero se
rechazarán importes negativos, fuera de rango o asignaciones superiores al total
registrado de una categoría. Un error conservará todos los datos del formulario.

«Costos completos» seguirá significando que ya se conocen los cargos del pedido.
En compras con seguimiento detallado, se calculará a partir de los estados
explícitos de los conceptos descritos abajo.
«Asignación pendiente / completa» será un estado calculado independiente. Esto
permite conservar el significado de las compras existentes. Solo se presentará un
costo como completo cuando ambos estados estén completos; en los demás casos se
indicará «Provisional» y, si corresponde, «Faltan gastos por asignar».

Editar o eliminar cargos obligará a revisar cualquier exceso antes de guardar.
Eliminar una línea retirará sus asignaciones y aumentará el saldo pendiente, sin
borrar cargos del pedido. Cambiar la cantidad mantendrá los gastos totales de esa
línea y recalculará el costo unitario. No se trasladarán gastos silenciosamente.

## Seguimiento visual aprobado

Cada categoría tendrá un estado explícito: Pendiente, Registrado o No aplica.
En pantalla, importation se llamará «Nacionalización / manejo» e incluirá la gestión;
taxes seguirá siendo «Impuestos». Se conservarán las claves de categorías actuales.
El filtro «Nacionalización pendiente» incluirá pedidos con cualquiera de esos dos
conceptos pendiente. Otros filtros permitirán consultar envío pendiente, cualquier
costo pendiente, asignación pendiente y completos, combinados con los actuales.

Una nueva compra comienza con las cuatro categorías pendientes. El usuario puede
marcar Otros costos como No aplica. Introducir un cargo no cierra automáticamente
su categoría: podrían faltar cargos adicionales. Registrado exige al menos una
fila de costo de esa categoría, incluso de importe cero; No aplica exige no tener
filas ni asignaciones. Se permite Pendiente con cargos parcialmente registrados.
Costos completos se calcula cuando no hay categorías pendientes.

Prioridad de los indicadores de la cabecera:
- Anulada: gris y texto, sin alertas de pendientes.
- Costos pendientes: naranja y nombres de los conceptos pendientes.
- Falta distribuir gastos: azul, si todos los conceptos están resueltos pero falta
  asignar parte de los gastos.
- Completo: verde, conceptos resueltos y asignación completa.

El color estará acompañado siempre por texto. Arriba se mostrará el contador
«N pedidos con costos pendientes» de los pedidos vigentes que cumplen los filtros
actuales, aclarando «en esta vista». No se usarán avisos rojos por antigüedad ni se
interpretarán estos estados como confirmación de pago o recepción física.

Persistir el seguimiento como cost_states_json nullable en purchases; NULL
identifica compras históricas sin seguimiento por concepto. En esas compras se
conserva costs_complete y no se inventan conceptos pendientes: mostrar «Revisar
conceptos pendientes» si eran incompletas. El filtro general las incluye; el de
nacionalización no afirma que les falte ese concepto. Al editar, ofrecer activar
el seguimiento explícito y revisar las cuatro categorías antes de guardarlo.
No permitir cambiar el estado global una vez activado el seguimiento detallado.
Las revisiones conservarán también los estados; los payloads antiguos normalizan
la ausencia de seguimiento a NULL. La migración se hará junto con el esquema 10.

## Cálculos y redondeo

Se conserva la conversión actual: cantidad por costo original, convertido una vez
a COP con Decimal y redondeo HALF_UP a centavos. Los cargos también se convierten
una sola vez y se suman por categoría para cotejar las asignaciones.

- Total de línea con gastos = subtotal COP de mercancía + gastos asignados.
- Compra por unidad = subtotal COP de mercancía / cantidad.
- Costo con gastos por unidad = total de línea con gastos / cantidad.

Los totales enteros en centavos son la fuente de verdad. Los valores unitarios
mostrados se redondean a dos decimales y se identifican como aproximados cuando
no dividen exactamente; nunca se reconstruirá el total multiplicando ese valor
redondeado. La futura asignación a máquinas individuales deberá repartir los
centavos residuales, pero queda fuera de esta entrega.

Ejemplo: modelo A, dos unidades de $1.000.000 y envío asignado $120.000;
modelo B, una unidad de $2.000.000 y envío asignado $180.000. Con un cargo registrado
de envío de $300.000, no hay saldo pendiente: A cuesta $1.060.000 por unidad y B
$2.180.000. Total del pedido: $4.300.000. Con costos por completar, ambos costos
unitarios siguen siendo provisionales.

## Persistencia y compatibilidad

Ampliar PurchaseLineInput con cuatro importes asignados, predeterminados en cero,
al final de sus campos actuales. Añadir cuatro columnas INTEGER NOT NULL DEFAULT 0
a purchase_lines, con restricciones de entero no negativo. La migración del
esquema 9 al 10 será transaccional, con respaldo previo y rechazo de versiones
futuras. Condicionar la creación actual de tablas de compras a version < 9.

Las compras existentes no recibirán repartos inventados. Con cargos positivos y
asignaciones cero, mostrarán saldo pendiente; sus totales y estados de costos no
cambiarán. Las compras sin cargos tendrán asignación completa por definición.

Create/update persistirán los importes junto con las líneas en la misma transacción.
Se conservarán la validación de pertenencia de líneas, la revisión optimista, la
anulación y la idempotencia existentes. Para solicitudes históricas, comparar
payloads normalizando los nuevos campos ausentes a cero, sin reescribir los datos
originales de la solicitud. Las instantáneas nuevas incluirán las asignaciones;
las antiguas se mostrarán como «Asignación no registrada» sin atribuirles un reparto.

## Integración y verificación

Los cálculos y comprobaciones vivirán en purchases.py; persistencia e historial en
purchases_repository.py y database.py; edición en purchase_line_editor.py y
purchase_dialog.py. El listado agrupado se implementará en purchases_page.py,
manteniendo la apertura por identificador del pedido.

Verificar pedidos mixtos e iguales, asignación parcial/completa/excesiva, cargos
USD con tasas distintas, cantidades modificadas, eliminación de líneas, ceros,
redondeos y límites. Verificar migración desde esquema 9, reapertura, rollback,
historial antiguo/nuevo, solicitudes repetidas y conservación de datos existentes.
En interfaz comprobar búsqueda y selección de filas hijas, totales sin duplicar,
errores sin pérdida de edición, selección de importes al primer clic y adaptación
a 1440×900, 1280×720 y pantalla pequeña. Usar exclusivamente datos temporales.

## Fuera de alcance

Recepción, tránsito, stock disponible, reservas, descuento al vender y etiquetas
individuales se incorporarán en la etapa de inventario. Allí se mostrará junto al
producto disponible / cantidad a vender / restante, con texto y colores. Esta
entrega no mostrará cantidades compradas como existencias disponibles ni alterará
ventas o movimientos de caja. No reconstruirá aún los paquetes de distribución.
