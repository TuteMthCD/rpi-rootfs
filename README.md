# rpi-rootfs

Script en Python para montar rápidamente una imagen de Raspberry Pi OS como si fuera un `sysroot` local. Descarga la imagen oficial, la expande, ata los dispositivos necesarios, inyecta `qemu-aarch64-static` y entra en un `chroot` arm64 listo para compilar o ejecutar tus proyectos.

## Dependencias

La herramienta necesita Python 3 y las utilidades que el script invoca (`curl`, `xz`, `losetup`, `mount`, `qemu-aarch64-static`, etc.). Instálalas antes de ejecutar `rpi-root.py`.

### Arch Linux

```bash
sudo pacman -S --needed python curl xz util-linux qemu-user zsh
# Para obtener qemu-aarch64-static instala el paquete community o AUR:
yay -S qemu-user-static
```

> `losetup`, `mount` y `umount` vienen en `util-linux`. Si usas otro helper AUR distinto a `yay`, cámbialo en el comando.

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install python3 curl xz-utils util-linux qemu-user-static binfmt-support
```

Estos paquetes proveen `losetup`, `mount`, `chroot` y el binfmt para ejecutar binarios arm64 mediante QEMU. 
## Uso básico

1. Clona o copia este repositorio y entra a la carpeta.
2. Ejecuta el script como root (requiere `sudo` porque monta dispositivos en `/mnt`). El argumento `--project-src` es obligatorio: apunta a tu carpeta local para bind-montarla dentro del chroot.
   ```bash
   sudo ./rpi-root.py \
     --project-src ~/tu-proyecto \
     --project-dst /opt/tu-proyecto \
     --mount-root /mnt/rpi-root \
     --mount-boot /mnt/rpi-boot
   ```
   Si no pasas `--project-dst`, se usará `/opt/build` como ruta dentro del chroot.
3. El script descargará la última imagen `raspios_lite_arm64`, la asociará a un loop device, montará las particiones `root` y `boot`, copiará `qemu-aarch64-static` dentro del chroot y bind-monteará `dev`, `proc`, `sys`, `run` y tu código (`--project-src` → `--project-dst`).
4. Entrarás en `/bin/bash` dentro del entorno ARM. Desde ahí puedes compilar con `sysroot=/mnt/rpi-root` o usar tus toolchains cruzados apuntando a las librerías reales del sistema.

El directorio `--mount-root` actúa como tu `sysroot`: define `SYSROOT=/mnt/rpi-root` en tus scripts de build, exporta `PKG_CONFIG_PATH=$SYSROOT/usr/lib/pkgconfig`, etc., y tendrás acceso a todas las cabeceras y librerías de la imagen.

## Limpieza y notas

- El script desmonta todo (proyecto, bind mounts, particiones y loop device) en el bloque `finally`. Si algo falla, desmonta manualmente con `sudo umount -l` y `sudo losetup -D`.
- Usa `--img-url` para fijar otra versión de Raspberry Pi OS y `--workdir` para reutilizar descargas existentes.
- Si necesitas ejecutar un build dentro del chroot, coloca tus scripts en `--project-src` y lánzalos desde el shell que abre el script.
