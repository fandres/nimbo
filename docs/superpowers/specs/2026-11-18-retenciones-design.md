# Informe de retenciones y certificados

Alcance aprobado: informe por período y cliente, factura, correo, valor retenido y seguimiento de certificados. El usuario eligió explícitamente estado por cliente y año. No generar beta ni enviar correos.

Se reutiliza Informes y su exportación PDF, con pestaña Retenciones y año actual por defecto. Se muestran solo ventas vigentes marcadas con retención; las anteriores mantienen su carácter informativo. Totales por cliente y año y detalle de facturas, identificación, correo, valor y tratamiento. Filtros de fecha, búsqueda y estado del certificado.

El estado anual se edita desde un gestor accesible en esa pestaña, con una fila por cliente/año, selector Pendiente de solicitar/Solicitado/Recibido y nota opcional. Guardar cada cambio es inmediato; no modifica ventas. La advertencia del gestor deja claro que la cifra puede estar filtrada, pero el estado afecta el año completo. Los estados se persisten y tienen registro de cambios.

Identidad: identificación recortada y normalizada en mayúsculas; no quitar dígito de verificación ni fusionar documentos distintos. Sin documento, usar nombre normalizado y avisar para completar identificación; no intentar unir automáticamente identidades distintas. Si se corrige la identificación, el nuevo grupo comienza pendiente y se conserva el seguimiento anterior.

Alternativas: estado por factura descartado por elección del usuario; gestor separado elegido para reutilizar la previsualización PDF y no saturar el informe con controles de edición. Sin lectura automática de certificados ni verificación tributaria.

Pruebas: agrupación y años, anuladas y sin retención excluidas, filtros, estados persistentes, historial, validación, documentos ausentes, escape HTML, PDF y UI. Migración 27 con respaldo y compatibilidad de restauración.
