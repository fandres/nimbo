# Inicio y navegación del negocio

Fecha: 18 de octubre de 2026.
Estado: aprobado por el usuario el 18 de octubre de 2026; implementado y verificado en la rama codex/catalogo.

## Objetivo

Convertir la ventana del catálogo en una aplicación con Inicio y navegación entre módulos. Al abrir, el usuario quiere reconocer la situación de su negocio y acceder rápidamente a registrar una venta. La referencia visual aportada sustituye la maqueta anterior: tarjetas amplias, jerarquía visual clara, menú compacto y acciones expresadas con verbos.

Esta entrega implementará la estructura visual y la navegación con el catálogo existente. Los movimientos financieros, compras, inventario y ventas se incorporarán en entregas posteriores, conectados a esta estructura.

## Dirección visual aprobada

Referencia: `docs/referencias/inicio-referencia-usuario.png`. Se conserva su organización, no sus cifras ni sus afirmaciones sobre el negocio.

- Fondo claro, tarjetas blancas redondeadas, tipografía legible y espacios amplios.
- Tarjeta principal en azul oscuro, botones y selección en un segundo azul más vivo. Paleta provisional: azul oscuro #142B50, azul principal #315FDA y azul suave #EAF0FF. Cuando se entregue el logo definitivo se ajustarán estos colores.
- Los colores de marca se centralizan en una paleta reutilizable; no se inferirá automáticamente una paleta a partir de cualquier imagen.
- Verde, rojo y ámbar representan estados financieros, independientemente de los colores del logo. También se indicarán con valores, signos y etiquetas, sin depender solo del color.
- Se conserva la ventana inicial horizontal de 1320 × 720 unidades lógicas y el mínimo de 800 × 560. El Inicio podrá desplazarse verticalmente cuando el espacio sea insuficiente; el formulario compacto de producto seguirá como está.

## Navegación

Menú lateral compacto con icono y texto, selección visible y navegación por teclado. El contenido central cambia dentro de la misma ventana, sin abrir ventanas independientes ni acumular pestañas por cada módulo.

Secciones visibles: Inicio, Ventas, Compras, Productos, Dinero, Informes y Configuración. Productos abrirá por ahora el catálogo; más adelante agrupará Catálogo e Inventario. Dinero agrupará cuentas, movimientos y gastos cuando esos módulos existan.

En esta entrega estarán habilitados Inicio y Productos. Las secciones futuras aparecerán identificadas como «Próximamente», deshabilitadas y con explicación accesible. No se simulará que una venta, un gasto o una compra se puede guardar.

Cambiar entre Inicio y Productos conservará los filtros y la selección del catálogo. El acceso Nuevo producto permanecerá en Productos; su atajo Ctrl+N tendrá ámbito del catálogo para no abrir un producto desde Inicio.

## Pantalla Inicio

1. Encabezado con fecha local y saludo neutro, sin deducir el nombre del negocio o del usuario de la identidad de Git.
2. Tarjeta principal «Ventas del mes». Antes de implementar ventas mostrará «Aún sin registros de ventas» y una explicación breve, sin montos inventados, comparaciones mensuales ni metas supuestas.
3. Tarjeta «Tu dinero» con estados explícitos «Cuentas por configurar» y «Cobros aún no disponibles». La ausencia del módulo no se interpretará como saldo cero.
4. Acciones principales: Nueva venta, Comprar o importar, Anotar un gasto y Cobrar. Se conservará el protagonismo visual de Nueva venta, pero las acciones financieras estarán deshabilitadas y marcadas «Próximamente» en esta entrega. Un acceso funcional «Ver catálogo» permitirá continuar el trabajo disponible.
5. Panel «Para hoy»: acceso al catálogo y su número real de productos/servicios activos. No se llamará a estos registros «máquinas disponibles» porque todavía no existe inventario físico.
6. Espacio «Flujo de caja neto»: estado vacío explicado hasta disponer de cobros y pagos reales. Sin curvas ficticias.
7. «Tus últimas ventas»: estado vacío, preparado para incorporar las ventas reales posteriormente.

Al regresar a Inicio se refrescará el recuento real del catálogo. Si la base no puede leerse, se mostrará un error recuperable en lugar de un recuento falso.

No se incluye todavía el buscador de acciones de la referencia: el menú y los accesos visibles cubren la navegación de esta entrega.

## Semántica del futuro gráfico

La solicitud del usuario se interpreta como flujo neto del período: cobros recibidos menos pagos realizados, agrupados por semana o mes. No equivale al saldo acumulado de una cuenta ni a la utilidad de las ventas.

La curva neta tendrá referencia visible en cero: segmentos positivos verdes, negativos rojos y una zona de proximidad a cero en ámbar. El umbral de esa zona será un parámetro explícito del futuro módulo financiero y se mostrará al usuario; no se decidirá arbitrariamente en esta entrega visual. Entradas y salidas podrán consultarse por separado, sin etiquetar toda salida como flujo neto negativo.

## Arquitectura y conservación de datos

- MainWindow pasa a ser el contenedor de navegación con QStackedWidget.
- Se extrae el catálogo existente a un widget propio, manteniendo sus operaciones, campos, filtros y formularios.
- Inicio será otro widget independiente que consume únicamente el recuento real del repositorio actual.
- El repositorio SQLite, sus rutas y su esquema 2 se conservan. No se migran ni modifican datos comerciales como parte de esta entrega.
- La carga opcional del logo ya existente continúa en la estructura principal. La edición del nombre y logo desde Configuración sigue registrada como entrega posterior.
- Los colores comunes se centralizan en el módulo de estilo para permitir adaptar la marca sin cambiar reglas financieras.

## Verificación

- Al abrir aparece Inicio; el acceso a Productos muestra el catálogo existente.
- Volver al catálogo conserva filtros y selección; crear o editar un producto funciona igual que antes.
- Volver a Inicio actualiza los recuentos; no hay números financieros ni existencias simuladas.
- Ctrl+N solo inicia un producto cuando el catálogo está activo.
- Las opciones futuras no ejecutan acciones ni muestran confirmaciones falsas.
- El logo ausente o inválido no impide abrir la aplicación.
- Pruebas de regresión del repositorio y del formulario, más pruebas de navegación y estado vacío.
- Capturas revisadas en tamaño inicial y mínimo, con datos exclusivamente temporales.

## Secuencia posterior

Tras aprobar este documento se prepara el plan de implementación. Después de esta entrega: compras e inventario, cuentas y ventas con cobros diferidos, y finalmente indicadores y gráficos alimentados por esos movimientos. La venta rápida tendrá fecha de hoy editable y precio real editable, separado del precio recomendado del catálogo.
