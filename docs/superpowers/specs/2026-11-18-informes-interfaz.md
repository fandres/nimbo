# Interfaz de informes

Se adapta la propuesta visual entregada por el usuario a los controles Qt existentes.

- Seis pestañas, exportación única en la cabecera de la página.
- Períodos rápidos: este mes, mes pasado, este año y personalizado mediante calendarios.
- Limpiar filtros restablece solo la pestaña activa; Retenciones comienza en el año actual.
- Filtros redistribuidos según el ancho disponible y sin cambiar su significado.
- Vista previa de solo lectura sobre fondo suave, totales destacados, estados con color
  y descripciones de filtros compactas. PDF y vista previa usan el mismo HTML.
- Actualizar y Gestionar certificados permanecen disponibles.
- Se conservan los cálculos, las advertencias del informe y la exportación atómica.

Se reutiliza QTextBrowser/QTextDocument para mantener la exportación existente sin
introducir un navegador. Sus tablas tienen un estilo equivalente al diseño; no se
imitan los bordes redondeados de las tarjetas HTML que este motor no admite.

Verificación: suite de 502 pruebas aprobada; posteriormente se agregó y comprobó
una regresión de redistribución de fechas (11 pruebas de la página aprobadas).
Revisión visual a 900, 1100 y 1400 píxeles y PDF de varias páginas con datos temporales.
No modifica datos reales ni genera una nueva beta.
