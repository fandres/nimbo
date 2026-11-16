# Alias opcional del proveedor

Nueva compra / Editar compra incorpora Alias del proveedor, opcional, junto al
nombre completo (hasta 100 caracteres). Se guarda con cada pedido y su historial;
no reemplaza el nombre legal ni modifica pedidos anteriores automáticamente.

La búsqueda de Compras encuentra por nombre o alias sin distinguir mayúsculas.
Las sugerencias de proveedor y alias muestran ambos datos y completan los dos al
seleccionarlas, incluso cuando se busca por parte del alias. El listado y la lista
de pedidos para registrar pagos muestran el alias junto al nombre.

Migración 17: columna supplier_alias con valor vacío para compras existentes,
respaldo y transacción. Normalización de solicitudes antiguas para conservar los
reintentos idempotentes. Pruebas de guardar/buscar/editar/historial, autocompletar,
alias vacío, migración y rollback; captura sintética de la cabecera revisada.
