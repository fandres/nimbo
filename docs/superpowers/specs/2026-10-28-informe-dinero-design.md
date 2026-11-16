# Informe PDF de movimientos de dinero

Continuación del desarrollo autorizado del flujo de caja e informes. La revisión
confirma que Resumen, Movimientos, Cuentas y el gráfico ya existen. Esta entrega
completa la exportación del listado filtrado de Dinero sin reconstruir ese módulo.

## Diseño
Botón Exportar PDF en Dinero → Movimientos, junto a la búsqueda. Diálogo nativo
para elegir destino, aviso de resultado dentro de la pantalla. Cancelar no escribe.
PDF A4 horizontal con título, fecha de generación, intervalo, cuenta y búsqueda,
resumen del flujo filtrado y tabla de movimientos con su origen, cuenta y valores.
El informe admite cero registros y varias páginas; texto largo debe envolver.

El listado coincide con repository.movements(start,end,account,query). Los totales
de flujo se calculan sobre esos mismos registros excluyendo tarjetas, pagos sin
cuenta y, para todas las cuentas, transferencias internas. La tabla mantiene esos
registros identificados con texto y muestra además sus totales propios. Nunca
presentar una reducción de deuda de tarjeta como entrada de efectivo ni la salida
de capital como gasto. No mostrar saldo actual mezclado con totales de búsqueda.
Las comisiones se mantienen en el cobro neto existente, sin descontarlas otra vez.

## Enfoque
Reutilizar QtGui/QTextDocument/QPdfWriter evita dependencias y cambios al paquete
MIT/LGPL actual. HTML escapado generado internamente, sin cargar archivos adjuntos
ni recursos externos. Guardado atómico con QSaveFile protege un informe anterior
si hay un error. Alternativa reportlab: adecuada, pero añade otra dependencia sin
necesidad para este informe. Elección técnica del implementador: Qt.

No modificar la base, adjuntos ni cálculos existentes; PDF de ventas con retención
y otros informes quedan como siguientes entregas del desarrollo por etapas.
