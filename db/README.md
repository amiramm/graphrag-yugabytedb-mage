# Database image

This builds a single-node YugabyteDB **2026.1** with the `vector` and `mage`
extensions, from a **native aarch64** AlmaLinux 8 release tarball.

## Get the tarball

The image is built from a packaged release tarball that is **not** committed to
this repo (it is ~500 MB). Place it in this directory before building:

```
db/yugabyte-2026.1.0.0-b109-almalinux8-aarch64.tar.gz
```

For YugabyteyteDB engineers, the 2026.1 packaged releases live in the
`releases.yugabyte.com` S3 bucket:

```bash
aws s3 cp \
  s3://releases.yugabyte.com/2026.1.0.0-b109/yugabyte-2026.1.0.0-b109-almalinux8-aarch64.tar.gz \
  db/
```

Any `yugabyte-2026.1.*-almalinux8-aarch64.tar.gz` works; pass the filename via
the `YB_TARBALL` build arg / `docker-compose.yml`.

> **Why native aarch64?** On Apple Silicon the published `amd64` image crashes
> under QEMU emulation (`yb-master` `mmap: Cannot allocate memory`). The native
> build runs at full speed.

## Build

```bash
docker build --platform linux/arm64 \
  --build-arg YB_TARBALL=yugabyte-2026.1.0.0-b109-almalinux8-aarch64.tar.gz \
  -t yb-graphrag:2026.1.0.0-b109 .
```

`docker compose up -d --build` from the repo root does this for you.
