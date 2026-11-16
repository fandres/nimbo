# Inicio y navegación

18 de octubre de 2026. Implementación en codex/catalogo conforme al diseño y plan aprobados.

## Comprobaciones

- Suite completa: 61 pruebas aprobadas con `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`.
- Inicio aparece al abrir; Productos conserva el catálogo y su formulario horizontal.
- Navegación repetida conserva filtros y selección. Ctrl+N solo abre un producto cuando Productos es la sección activa, incluso si el foco sigue en el menú lateral. No abre un segundo formulario sobre uno modal.
- Inicio consulta productos/servicios activos reales. Ante un bloqueo se retiran los recuentos anteriores, se informa el error y Reintentar recupera la lectura.
- Acciones y módulos financieros pendientes deshabilitados; no se generan importes, ventas ni curvas ficticias.
- Arranque en proceso separado, logo ausente/inválido y conservación de rutas de datos verificados.
- Capturas Qt revisadas: tamaño inicial 1320 × 720, vista ampliada 1320 × 1120, Inicio y catálogo a 800 × 560. Inicio se adapta en columnas y admite desplazamiento vertical sin desplazamiento horizontal.
- No hubo cambios en el repositorio SQLite ni su esquema. Las capturas usan bases temporales.

## Decisiones técnicas

El atajo usa QShortcut asociado a CatalogPage, con contexto WindowShortcut y habilitación explícita únicamente cuando Productos es la sección activa. La revisión independiente detectó que limitarlo a WidgetWithChildrenShortcut impedía usarlo con el foco en el menú. Se reprodujo el fallo, se corrigió y se comprobó la supresión durante un formulario modal. La navegación y las tarjetas se implementaron conjuntamente al compartir la interfaz HomePage; sus comportamientos se probaron inicialmente en rojo y después en verde. El formato de fecha usa un literal para «de», con regresión verificada.

## Límites

La verificación funcional usa Qt offscreen, no automatización del escritorio nativo. Las capturas muestran la aplicación implementada, no una imagen generada. Ventas rápidas, movimientos, gráficos financieros, configuración de marca desde la interfaz y AppImage siguen pendientes para sus respectivas entregas.

Revisión independiente completada: sin hallazgos críticos o importantes; la observación de teclado fue corregida con una regresión que falló antes del cambio. No quedan observaciones pendientes.

## Ajuste de espacio y alineación — 18 de octubre de 2026

- Inicio completo visible a 1320 × 720 píxeles lógicos, sin desplazamiento horizontal ni vertical; la prueba anterior reproducía un exceso vertical de 282 píxeles.
- Tamaño inicial calculado con el área disponible de la pantalla, respetando el escalado de Qt.
- Menú lateral con iconos sobre las etiquetas, centrados y con posiciones uniformes en módulos disponibles y futuros.
- Tarjetas con márgenes menores y leyenda del flujo de caja en una fila. Se conserva el desplazamiento en pantallas pequeñas.
- Verificación: 63 pruebas aprobadas con Qt offscreen y revisión visual de `docs/capturas/inicio.png` a 1320 × 720. No se modificó la base de datos personal.

### Acceso principal a nueva venta (19 de octubre de 2026)

Botón «Nueva venta» de mayor tamaño (mínimo 260×64), azul y texto destacado en el encabezado, visible al abrir Inicio. Verificados su apertura del formulario y que el resumen con tres ventas siga cabiendo a 1320×720.
