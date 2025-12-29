#!/usr/bin/env python3
import argparse
import os
import pathlib
import subprocess
import sys


def run(cmd, check=True, **kwargs):
    print(f"\n==> {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, **kwargs)


def require_root():
    if os.geteuid() != 0:
        sys.exit("Este script necesita privilegios de root (sudo).")


def ensure_file(path, url):
    """Download url into path if the file is missing."""
    if path.exists():
        print(f"Archivo {path.name} presente, reutilizando")
        return
    run(["curl", "-L", url, "-o", str(path)])


def download_image(workdir, url):
    img = workdir / "raspios.img"
    if img.exists():
        print("Imagen ya descargada, reusando raspios.img")
        return img

    xz_path = workdir / "raspios.img.xz"
    ensure_file(xz_path, url)

    run(["xz", "-dkf", str(xz_path)])
    raw_img = next(workdir.glob("*.img"))
    raw_img.rename(img)
    return img


def attach_loop(img):
    out = subprocess.check_output(["losetup", "-Pf", "--show", str(img)], text=True).strip()
    return out


def mount_partitions(loop_dev, mnt_root, mnt_boot):
    for path in (mnt_root, mnt_boot):
        path.mkdir(parents=True, exist_ok=True)
    run(["mount", f"{loop_dev}p2", str(mnt_root)])
    run(["mount", f"{loop_dev}p1", str(mnt_boot)])


def bind_mounts(mnt_root):
    for target in ("dev", "proc", "sys", "run"):
        run(["mount", "--bind", f"/{target}", str(mnt_root / target)])

def bind_project(project_src, mnt_root, project_dst):
    if not project_src.exists():
        raise FileNotFoundError(f"Proyecto no encontrado: {project_src}")
    dst_inside = mnt_root / project_dst.lstrip('/')
    dst_inside.parent.mkdir(parents=True, exist_ok=True)
    dst_inside.mkdir(parents=True, exist_ok=True)
    run(["mount", "--bind", str(project_src), str(dst_inside)])
    return dst_inside

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--img-url", default="https://downloads.raspberrypi.com/raspios_lite_arm64_latest")
    parser.add_argument("--workdir", default=os.environ.get("PWD", os.getcwd()))
    parser.add_argument("--mount-root", default="/mnt/rpi-root")
    parser.add_argument("--mount-boot", default="/mnt/rpi-boot")
    parser.add_argument("--project-src", default="/home/tute/Documents/tmc5130")
    parser.add_argument("--project-dst", default="/opt/tmc5130")
    parser.add_argument("--build-script", default="build-rpi.sh")
    args = parser.parse_args()

    require_root()
    workdir = pathlib.Path(args.workdir).expanduser()
    workdir.mkdir(parents=True, exist_ok=True)
    img = download_image(workdir, args.img_url)

    loop_dev = attach_loop(img)
    try:
        mnt_root = pathlib.Path(args.mount_root)
        mnt_boot = pathlib.Path(args.mount_boot)
        mount_partitions(loop_dev, mnt_root, mnt_boot)
        run(["cp", "/usr/bin/qemu-aarch64-static", str(mnt_root / "usr/bin/")])
        bind_mounts(mnt_root)
        project_src = pathlib.Path(args.project_src).expanduser().resolve()
        project_dst = bind_project(project_src, mnt_root, args.project_dst)
        run(["chroot", str(mnt_root), "/bin/zsh"])
    finally:
        if 'project_dst' in locals() and pathlib.Path(project_dst).exists():
            run(["umount", str(project_dst)], check=False)
        for target in ("run", "sys", "proc", "dev"):
            mount_path = pathlib.Path(args.mount_root) / target
            if mount_path.is_mount():
                run(["umount", str(mount_path)], check=False)
        for mount_point in (args.mount_boot, args.mount_root):
            if pathlib.Path(mount_point).is_mount():
                run(["umount", mount_point], check=False)
        run(["losetup", "-d", loop_dev], check=False)


if __name__ == "__main__":
    main()
