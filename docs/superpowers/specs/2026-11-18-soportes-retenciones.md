# Soportes de certificados anuales

Alcance aprobado: adjuntar PDF o imágenes por cliente/año, guardar copias organizadas,
consultarlas desde el gestor y ofrecer marcar Recibido después de adjuntar.

Se reutiliza el repositorio y diálogo de adjuntos, ampliando el propietario con
retention_certificate. La migración 28 añade un identificador estable por cliente/año
independiente de la revisión del estado. No se usa el rowid de la tabla de estados.
Documentos/<año>/Retenciones/cliente-<id>/ contiene las copias con nombres únicos.

El clip muestra el número de soportes activos. Adjuntar ofrece cambiar a Recibido;
solo aceptar actualiza el estado y su historial, con el control de revisión existente.
Una copia fallida no ofrece cambiar de estado. Un conflicto de revisión conserva la
copia y muestra el error. Quitar conserva la copia física y no cambia el estado.
Los respaldos existentes incluyen las copias y la asociación anual.

Verificación: aislamiento entre clientes y años, original intacto, quitar y restaurar,
copia fallida, confirmación aceptada/rechazada, conflicto de revisión y rollback de
migración. Revisión visual del gestor y diálogo con datos temporales.
Sin lectura automática, envío de correo, publicación ni generación de beta.
