> Documento original de la alfa 0.1. Las recetas siguen siendo aplicables; para la entrega actual, consulta [alfa-0.4.md](alfa-0.4.md).

# Nimbo 0.1.0-alpha.1 — preparación de distribución

Objetivo: compartir una alpha local con usuarios de Debian 13 y Windows 11,
ambos Intel/AMD x86-64. ARM no forma parte de esta entrega. El AppImage Linux y el ZIP Windows ya están generados. La prueba visual en los
equipos Debian 13 y Windows 11 del destinatario sigue pendiente.

## Identidad y datos

Nombre de software: Nimbo. Versión Python: 0.1.0a1, visible: 0.1.0-alpha.1.
«Mi negocio» sigue representando el negocio del usuario, separado de Nimbo.
Conservar organization=Fandres/application=MiNegocio evita mover o perder de vista
bases existentes. No se incluye la base del desarrollador ni su logo en los paquetes.
La base permanece fuera del ejecutable y recibe respaldo antes de migraciones.

## Construcción nativa

Se usa PyInstaller en modo carpeta, con Python 3.13, PySide6 6.12.0 y
PyInstaller 6.22.3. Las versiones directas están en packaging/requirements.txt;
el manifiesto final registra todas las versiones transitivas instaladas. No es
una compilación bit a bit reproducible. Windows se construye con Python y PyInstaller de Windows; pueden ejecutarse en
Windows nativo o en Wine, registrando cuál se utilizó.

### Debian 13

Usar una máquina/VM Debian 13 x86-64 con escritorio para la prueba final. Para
construir bastan Python 3.13 con venv, binutils y las bibliotecas gráficas de Qt.
En una instalación mínima, preparar como administrador:

```sh
apt install python3-venv file libgtk-3-0t64 libpython3.13 libgssapi-krb5-2 binutils libglib2.0-0t64 libfontconfig1 libfreetype6 libsm6 libice6 libxext6 libxrender1 libx11-xcb1 desktop-file-utils libgl1 libegl1 libdbus-1-3 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxcb-xinerama0 libxcb-render-util0 libwayland-client0 libwayland-cursor0 libwayland-egl1 fonts-dejavu-core
```

Desde el repositorio:

```sh
python3 -m venv .venv-build
.venv-build/bin/python -m pip install -r packaging/requirements.txt
```

Descargar appimagetool x86-64 y un runtime type-2 x86-64 desde sus repositorios
oficiales. Conservar los archivos y sus versiones/checksums para repetir el build:

- https://github.com/AppImage/appimagetool/releases
- https://github.com/AppImage/type2-runtime/releases

Dar permiso de ejecución a appimagetool y proporcionar sus rutas absolutas:

```sh
.venv-build/bin/python packaging/build.py --appimagetool /ruta/appimagetool-x86_64.AppImage --runtime /ruta/runtime-x86_64
```

La receta rechaza construir el AppImage en CachyOS para no anunciar falsamente
compatibilidad con Debian 13 usando bibliotecas más nuevas del equipo de desarrollo.
No descarga herramientas automáticamente ni modifica el sistema.

### Windows 11

Instalar Python 3.13 x64 para construir (el destinatario no necesita Python).
En PowerShell, desde el repositorio:

```powershell
py -3.13 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r packaging\requirements.txt
.\.venv-build\Scripts\python.exe packaging\build.py
```

Produce un ZIP con la carpeta Nimbo, Nimbo.exe y sus bibliotecas. Para esta
alpha se evita un instalador: extraer y abrir. No se publica ni firma automáticamente.

## Comprobaciones y entregables

El script congela solo el punto de entrada y sus dependencias, agrega instrucciones
y los archivos de licencias encontrados en los paquetes. Ejecuta `--smoke-test`
con Qt offscreen y una SQLite temporal; nunca utiliza la base personal para probar.
En Linux también prueba el AppImage final extraído. Genera SHA-256 y manifiesto JSON.
Un binario sin manifiesto con smoke_test=passed no es una entrega validada.

Resultados previstos en dist/:
- Nimbo-0.1.0-alpha.1-linux-x86_64.AppImage
- Nimbo-0.1.0-alpha.1-windows-x86_64.zip
- archivos .sha256 y .json de cada entrega.

Antes de compartir hay que ejecutar el paquete en un escritorio limpio de Debian
13 y en Windows 11, sin Python instalado: abrir, crear venta ficticia, cerrar,
reabrir, verificar persistencia y probar escala 100/150 %. Probar Linux X11 y
Wayland según el escritorio del destinatario. Registrar resultados, versiones y
checksums; la prueba automática no reemplaza esta comprobación visual.

Las bibliotecas de Qt se incluyen dinámicamente. Conservar avisos de terceros y
revisar las licencias de las dependencias incluidas antes de distribuir públicamente.

## Referencias técnicas

- https://pyinstaller.org/en/stable/requirements.html
- https://pypi.org/project/pyinstaller/ (construcción nativa por sistema)
- https://docs.appimage.org/reference/best-practices.html (base Linux compatible)
- https://doc.qt.io/qtforpython-6/deployment/index.html

## Estado comprobado el 19 de octubre de 2026

En el equipo de desarrollo: 130 pruebas aprobadas, arranque temporal sin acceder
a la base personal, `--version`, ayuda de empaquetado y compilación sintáctica.
La receta rechazó correctamente construir el AppImage fuera de Debian 13.
AppImage generado dentro de un entorno Debian 13 aislado con Bubblewrap:
`dist/Nimbo-0.1.0-alpha.1-linux-x86_64.AppImage` (aproximadamente 63 MB).
También pasaron las 130 pruebas dentro de Debian 13. El ejecutable y el AppImage
superaron `--smoke-test`; el AppImage arrancó en otra base Debian sin Python,
con bibliotecas gráficas del sistema. La comprobación SHA-256 pasó.

SHA-256 del AppImage:
`0bd96f11362573b321fe7d2a7666118a62b6c48e6d2b31d93abaa18aaf130c47`

La prueba automática usa Qt offscreen: no valida todavía el escritorio real,
X11/Wayland, escala ni apertura por doble clic. Seguir `PRUEBA-DEBIAN13.txt`
en el equipo de ventas. El ZIP de Windows se generó posteriormente; ver la validación del 20 de octubre.

### Entorno aislado utilizado

`packaging/in_debian13.sh` ejecuta comandos en el rootfs ya preparado bajo
`build/debian13/rootfs`, sin instalar paquetes en el anfitrión. Requiere Bubblewrap
y espacios de nombres de usuario habilitados. El directorio build está ignorado
por Git; este auxiliar no descarga ni prepara el rootfs por sí solo.

Base oficial: debuerreotype/docker-debian-artifacts, dist-amd64/trixie/slim,
archivo OCI `rootfs.tar.gz`, SHA-256:
`ecc510c1e359bdc007b39802570bb7e4dec7d6ebccf357c3201a74299113e05e`.
Python 3.13.5, PySide6 6.12.0, PyInstaller 6.22.3. El manifiesto JSON junto al
AppImage registra las versiones y los checksums de las herramientas. El kernel
es el del anfitrión, compartido por el aislamiento; las bibliotecas son Debian.

Para verificar el archivo desde la carpeta dist:

```sh
sha256sum -c Nimbo-0.1.0-alpha.1-linux-x86_64.AppImage.sha256
```

## Construcción Windows mediante Wine

En un anfitrión Linux con Wine, es posible ejecutar las herramientas **de Windows**
en un prefijo separado. No utiliza el PyInstaller ni el Python de Linux para
crear el EXE. Esta alternativa no valida la compatibilidad visual en Windows 11.

Preparación utilizada: Wine 11.20, Python 3.13.5 x64 oficial instalado en
`C:\Python313`, dentro de `build/windows/prefix`. No se usa el prefijo personal
`~/.wine`. Instalar Python sin launcher ni cambios en PATH; después:

```sh
bash packaging/in_wine.sh -m pip install -r packaging/requirements.txt pytest pytest-qt
QT_QPA_PLATFORM=offscreen bash packaging/in_wine.sh -m pytest -q
bash packaging/in_wine.sh packaging/build.py --execution-environment wine
```

El campo `execution_environment` del manifiesto deja constancia de Wine.
El nombre de Windows que Wine comunica en `build_os` no certifica que se haya
probado un escritorio real de esa versión. La guía `PRUEBA-WINDOWS11.txt` se
incluye en el ZIP para realizar esa comprobación en el equipo del destinatario.

## Validación Windows — 20 de octubre de 2026

Artefacto: `dist/Nimbo-0.1.0-alpha.1-windows-x86_64.zip`, aproximadamente 45 MB.
Contiene Nimbo.exe x86-64, sus dependencias, licencias y la guía de evaluación.
SHA-256: `1c124e65ee918b82f7d0d6dffd9061743fc085cfdb8651ef786df7d7fa843727`.

- 130 pruebas aprobadas con Python 3.13.5 y Qt Windows bajo Wine 11.20.
- 130 pruebas aprobadas también en Linux tras adaptar las pruebas de rutas.
- Integridad ZIP y SHA-256 comprobadas; sin bases de datos comerciales incluidas.
- ZIP extraído y EXE arrancado con `--smoke-test` en otro prefijo Wine sin Python
  instalado. SQLite temporal, Qt offscreen; salida 0. También pasó el arranque
  con el plugin gráfico Windows de Qt bajo Wine.
- **Windows 11 real pendiente**: apertura con doble clic, escala, apariencia,
  permisos y persistencia según la guía incluida. La alpha no tiene firma digital.

Las pruebas antes dependían de XDG_DATA_HOME incluso al ejecutarse en Windows.
Ahora comprueban la ruta Windows sin escribir allí y aíslan las bases de prueba
en directorios temporales. No se cambió la ubicación de datos de la aplicación.
