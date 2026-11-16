# Inicio y navegación — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Abrir la aplicación en un Inicio moderno y navegar al catálogo existente sin perder su estado ni modificar datos comerciales.

**Architecture:** MainWindow contiene menú lateral y QStackedWidget. CatalogPage conserva la lógica actual del catálogo; HomePage presenta estados financieros vacíos y recuentos reales. La capa de datos permanece intacta.

**Tech Stack:** Python, PySide6/Qt Widgets, SQLite existente, pytest y pytest-qt.

**Spec:** ../specs/2026-10-18-inicio-navegacion-design.md, aprobado el 18 de octubre de 2026. Referencia visual: docs/referencias/inicio-referencia-usuario.png.

## Restricciones generales

- Tamaño inicial 1320 × 720; mínimo 800 × 560. Inicio admite desplazamiento vertical.
- Azul oscuro #142B50, azul principal #315FDA y azul suave #EAF0FF. Estados financieros verde/rojo/ámbar independientes de la marca.
- Inicio y Productos habilitados; Ventas, Compras, Dinero, Informes y Configuración visibles como Próximamente, deshabilitados.
- No cifras financieras, gráficas, metas ni comparaciones ficticias. Recuento del catálogo nunca presentado como existencias físicas.
- No cambios en esquema 2, ruta SQLite, códigos, precios, listas compartidas ni formulario horizontal.
- Logo opcional; saludo neutro y fecha local. No inferir nombre del usuario a partir de Git.
- Ejecución directa en la carpeta y rama actuales, según la preferencia ya indicada por el usuario.

## Focos de revisión

1. Ctrl+N con Inicio activo: no debe abrir productos ni ejecutarse dos veces después de navegar; tarea 2.
2. Base bloqueada al volver a Inicio: no mostrar cero como recuento válido y permitir reintentar; tarea 3.
3. Filtros y selección tras navegar: conservarlos sin recrear CatalogPage; tarea 2.
4. Pantalla pequeña, escalado o textos largos: acceso por teclado y desplazamiento a todas las tarjetas sin cortar acciones; tarea 4.
5. Venta y saldo aún inexistentes: estados vacíos inequívocos y botones futuros que no guardan nada; tareas 2–3.

## Archivos

- src/mi_negocio/ui/catalog_page.py: catálogo extraído como QWidget, con métodos y widgets existentes.
- src/mi_negocio/ui/main_window.py: ventana, logo, menú y navegación.
- src/mi_negocio/ui/home_page.py: tarjetas, estados vacíos, fecha y recuentos.
- src/mi_negocio/ui/style.py: paleta centralizada y estilos de tarjetas/navegación.
- tests/test_ui.py: adaptar fixture para probar CatalogPage directamente, conservando assertions funcionales.
- tests/test_navigation.py: navegación, atajos y estados de Inicio.
- tests/test_app.py: adaptar comprobación de logo a la ventana con Inicio.
- README.md, docs/verificacion-inicio.md y docs/capturas/: instrucciones y evidencia visual de la entrega.

### Tarea 1: separar el catálogo de la ventana

**Interfaces:** CatalogPage(repository: CatalogRepository, parent: QWidget | None = None), hereda QWidget. Conserva refresh_products() -> bool, sus acciones y widgets públicos usados en tests. MainWindow(repository, logo_path=None) mantiene su firma para app.py.

- [x] Adaptar la fixture de tests/test_ui.py para instanciar CatalogPage en una ventana temporal del tamaño apropiado. Conservar todas las pruebas de edición, filtros, listas, validación y formulario sin desplazamiento.
- [x] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_ui.py -q` y observar el fallo por clase todavía inexistente.
- [x] Extraer el contenido central y sus métodos a catalog_page.py; quitar únicamente la responsabilidad de ventana/barra lateral. La página recibe el repositorio, sin abrir ni cerrar su conexión. MainWindow aloja provisionalmente esta página. Adaptar test_app para acceder a window.catalog_page en lugar de atributos antiguos de la ventana.
- [x] Ejecutar toda la suite y comprobar que las operaciones persisten exactamente igual. Guardar commit de refactor.

### Tarea 2: menú lateral y cambio de páginas

**Interfaces:** MainWindow.catalog_page: CatalogPage; MainWindow.home_page: HomePage; MainWindow.pages: QStackedWidget; MainWindow.nav_buttons: dict[str, QAbstractButton]; MainWindow.navigate(page: str) -> None para claves home/catalog. HomePage.open_catalog = Signal(). HomePage(repository, parent=None) y refresh_summary() -> None se crean inicialmente con estado vacío mínimo; tarea 3 completa su contenido.

- [x] Escribir pruebas de arranque en Inicio, paso a Productos, regreso conservando filtros y selección, navegación por teclado y secciones futuras deshabilitadas. Añadir prueba Ctrl+N en Inicio (sin diálogo) y Productos (un diálogo), incluso después de varias transiciones.
- [x] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_navigation.py -q` y observar fallos antes de implementar navegación.
- [x] Crear el menú compacto con icono y texto, selección exclusiva y foco visible. Reutilizar cada página en QStackedWidget. Mantener logo opcional y tamaño de la ventana. Encapsular el atajo del catálogo mediante Qt.WidgetWithChildrenShortcut para impedir activación desde Inicio.
- [x] Conectar Ver catálogo con navigate('catalog'); al entrar en Inicio llamar refresh_summary(). Etiquetar y deshabilitar secciones futuras con explicaciones accesibles. No abrir pantallas vacías como si fueran módulos operativos.
- [x] Ejecutar suite completa y guardar commit de navegación.

### Tarea 3: Inicio y estados reales

**Interfaces:** HomePage.refresh_summary() consulta repository.list_products(active=True); actualiza etiquetas separadas de productos y servicios activos. HomePage.catalog_button abre catálogo mediante señal; HomePage.retry_button reintenta la lectura. La fecha usa QDate.currentDate() y QLocale español para el texto.

- [x] Escribir pruebas con dos productos activos, un servicio activo y un producto inactivo: Inicio muestra 2 productos y 1 servicio, y actualiza después de cambios al volver. Verificar que no muestra valores de saldo/ventas inventados y que Nueva venta/Comprar/Anotar gasto/Cobrar están deshabilitados.
- [x] Probar bloqueo SQLite real: después de un recuento correcto, bloquear y refrescar; deben ocultarse los recuentos anteriores y mostrarse error. Liberar y pulsar Reintentar restaura los recuentos actuales.
- [x] Ejecutar pruebas nuevas y observar fallos; implementar tarjetas según la referencia: ventas destacadas en azul oscuro, Tu dinero, acciones rápidas, Para hoy, Flujo de caja neto y Tus últimas ventas. Usar textos vacíos del diseño. Dar a Ver catálogo una acción real y clara.
- [x] Centralizar paleta en style.py. Las tarjetas futuras deben conservar jerarquía visual sin aparentar disponibilidad. El espacio del gráfico explica que se conectará a cobros y pagos; no dibujar series ficticias.
- [x] Ejecutar suite completa y guardar commit del Inicio.

### Tarea 4: integración y revisión visual

**Interfaces:** Se mantiene app.main() y abrir.sh. El cierre de repositorio continúa bajo responsabilidad de app.main().

- [x] Verificar arranque en proceso separado, logo ausente/inválido y datos persistentes fuera del proyecto con tests/test_app.py. Añadir cobertura de acceso al final del Inicio por desplazamiento en tamaño mínimo y navegación con Tab hacia las acciones disponibles.
- [x] Ejecutar `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`; corregir regresiones antes de continuar.
- [x] Generar y revisar capturas de Inicio vacío, Inicio con recuentos temporales, catálogo y ventana mínima. Comprobar textos, contraste, foco, controles futuros deshabilitados y ausencia de desplazamiento horizontal en Inicio.
- [x] Actualizar README con qué está disponible y qué sigue pendiente. Registrar resultados y límites de las comprobaciones en docs/verificacion-inicio.md. No migrar ni poblar la base real para capturas.
- [x] Revisar diff completo y solicitar una revisión independiente según la guía activa. Corregir hallazgos accionables con sus regresiones; ejecutar suite final y git diff --check. Guardar commit de entrega en la rama actual.

## Revisión del plan

Las cuatro tareas cubren la especificación sin ampliar el alcance a ventas o contabilidad. La referencia verde se adapta a azules; el gráfico financiero real y su umbral de cercanía a cero quedan para el módulo de movimientos. Se conserva el método de ejecución directa ya elegido; falta la revisión de este plan antes de empezar a implementarlo.

## Cierre de ejecución

Implementado y comprobado con 61 pruebas. Ajuste tras revisión: el atajo usa WindowShortcut habilitado solo en Productos, para funcionar también con foco en el menú lateral. El detalle y las capturas están en docs/verificacion-inicio.md.
