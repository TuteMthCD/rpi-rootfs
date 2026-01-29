#!/usr/bin/env python3
import argparse
import os
import pathlib
import subprocess
import sys
import shutil


def run(cmd, check=True, **kwargs):
    print(f"\n==> {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, **kwargs)


def require_root():
    if os.geteuid() != 0:
        sys.exit("Este script necesita privilegios de root (sudo).")


def attach_loop(img):
    out = subprocess.check_output(["losetup", "-Pf", "--show", str(img)], text=True).strip()
    return out


def mount_partitions(loop_dev, mnt_boot):
    mnt_boot.mkdir(parents=True, exist_ok=True)
    run(["mount", f"{loop_dev}p1", str(mnt_boot)])


def pick_boot_files(mnt_boot):
    kernel = mnt_boot / "kernel8.img"
    dtb = mnt_boot / "bcm2711-rpi-4-b.dtb"
    initramfs = mnt_boot / "initramfs8"
    if not kernel.exists():
        sys.exit(f"No se encontro kernel8.img en {mnt_boot}")
    if not dtb.exists():
        sys.exit(f"No se encontro bcm2711-rpi-4-b.dtb en {mnt_boot}")
    return kernel, dtb, initramfs if initramfs.exists() else None


def ensure_qemu():
    path = shutil.which("qemu-system-aarch64")
    if not path:
        sys.exit("No se encontro qemu-system-aarch64. Instala qemu-system-arm.")
    return path


def ensure_qemu_img():
    path = shutil.which("qemu-img")
    if not path:
        sys.exit("No se encontro qemu-img. Instala qemu-utils.")
    return path


def next_power_of_two_gib(size_bytes):
    gib = 1024 ** 3
    size_gib = (size_bytes + gib - 1) // gib
    power = 1
    while power < size_gib:
        power <<= 1
    return power * gib


def ensure_sd_size(img, allow_resize=True):
    size_bytes = img.stat().st_size
    target_bytes = next_power_of_two_gib(size_bytes)
    if target_bytes == size_bytes:
        return
    if not allow_resize:
        sys.exit(
            f"Tamano de imagen {size_bytes} bytes no es potencia de 2 en GiB. "
            f"Redimensiona a {target_bytes} bytes o usa --auto-resize."
        )
    qemu_img = ensure_qemu_img()
    print(f"Redimensionando imagen a {target_bytes} bytes (power-of-2 GiB)...")
    run([qemu_img, "resize", str(img), str(target_bytes)])


def ensure_machine_supported(qemu, machine):
    try:
        out = subprocess.check_output([qemu, "-machine", "help"], text=True)
    except Exception:
        return
    if machine not in out:
        sys.exit(f"El QEMU instalado no soporta la maquina '{machine}'.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--img", default="raspios.img")
    parser.add_argument("--mount-boot", default="/mnt/rpi-boot")
    parser.add_argument("--ram", default="2048")
    parser.add_argument("--cpus", default="4")
    parser.add_argument("--machine", default="raspi4b")
    parser.add_argument("--extra-args", default="", help="Args extra para el kernel (cmdline).")
    parser.add_argument("--no-resize", action="store_true", help="No redimensionar la imagen.")
    parser.add_argument("--headless", action="store_true", help="Ejecutar sin ventana (serial en stdout).")
    args = parser.parse_args()

    require_root()
    img = pathlib.Path(args.img).expanduser()
    if not img.exists():
        sys.exit(f"Imagen no encontrada: {img}")

    ensure_sd_size(img, allow_resize=not args.no_resize)
    loop_dev = attach_loop(img)
    mnt_boot = pathlib.Path(args.mount_boot)
    try:
        mount_partitions(loop_dev, mnt_boot)
        kernel, dtb, initramfs = pick_boot_files(mnt_boot)
        qemu = ensure_qemu()
        ensure_machine_supported(qemu, args.machine)
        kernel_append = "root=/dev/mmcblk0p2 rw rootwait console=serial0,115200 console=ttyAMA0"
        if args.extra_args:
            kernel_append = f"{kernel_append} {args.extra_args}".strip()
        cmd = [
            qemu,
            "-M",
            args.machine,
            "-cpu",
            "cortex-a72",
            "-m",
            args.ram,
            "-smp",
            args.cpus,
            "-kernel",
            str(kernel),
            "-dtb",
            str(dtb),
            "-drive",
            f"if=sd,format=raw,file={img}",
            "-append",
            kernel_append,
            "-serial",
            "stdio",
            "-netdev",
            "user,id=net0,hostfwd=tcp::2222-:22",
            "-device",
            "usb-net,netdev=net0",
        ]
        if args.headless:
            cmd += ["-display", "none"]
        if initramfs:
            cmd += ["-initrd", str(initramfs)]

        run(cmd)
    finally:
        if mnt_boot.is_mount():
            run(["umount", str(mnt_boot)], check=False)
        run(["losetup", "-d", loop_dev], check=False)


if __name__ == "__main__":
    main()
