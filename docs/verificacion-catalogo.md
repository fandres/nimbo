# Verificación de la primera entrega

17 de octubre de 2026. Rama: codex/catalogo.

- 42 pruebas aprobadas con `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`.
- Instalación editable del paquete y compilación Python comprobadas.
- Capturas Qt revisadas: catálogo vacío, catálogo con datos temporales, ventana 800 × 560, formulario y errores de validación.
- Lanzador `abrir.sh` iniciado en el escritorio sin errores de arranque. No se automatizaron interacciones del escritorio nativo; la comprobación funcional se realizó con Qt offscreen.
- Revisión independiente de código realizada; verificó además el orden de tabulación.
- Se reprodujeron y corrigieron dos hallazgos con pruebas que fallaron antes del cambio: aviso de almacenamiento obsoleto tras recuperación y crecimiento del formulario al mostrar errores. Se priorizaron por la confusión del aviso y el riesgo de ocultar botones en pantallas pequeñas. La modificación del formulario añade desplazamiento y conserva los botones visibles; la suite completa comprueba regresiones.
- Sin hallazgos pendientes de esa revisión. AppImage y módulos posteriores están fuera de esta primera entrega.

Las capturas de demostración no contienen datos del catálogo real. Se conserva el desarrollo en su rama, sin publicar ni fusionar.

## Ampliación: marcas, subtipos y precio recomendado

- Diseño aprobado en conversación: listas editables compartidas, filtros combinables y un único precio recomendado; sin cambiar importes existentes.
- 51 pruebas aprobadas. Se verifican migración desde esquema 1, reapertura, opciones reutilizables, renombrado con asociaciones estables, cancelación sin crear opciones y rollback al intentar guardar un código duplicado.
- Revisión independiente: corregida la acción de Enter al renombrar; prueba observada fallar y pasar. Ajustado el espaciado al añadir filtros para conservar filas completas y el mensaje vacío a 800 × 560; capturas verificadas.
- Los datos de ejemplo solo se crearon en bases temporales. La base del usuario se actualizará al reiniciar la aplicación, no durante las pruebas.

## Formulario horizontal

Solicitud del usuario: completar el producto sin bajar la barra de desplazamiento. Se reorganizan los campos en tres filas de dos columnas: código/nombre, tipo/subtipo y marca/precio recomendado. Tamaño inicial 820 × 560 unidades lógicas, con altura limitada por la pantalla. Los botones permanecen fuera del área desplazable; esta queda como respaldo para pantallas pequeñas o mensajes de error extensos.

52 pruebas aprobadas, incluida una prueba que verifica todos los campos visibles y ausencia de desplazamiento vertical al abrir. Captura revisada: `docs/capturas/formulario-horizontal.png`. La navegación con Tab sigue el orden de lectura por filas.
