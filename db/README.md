# Database image (optional)

**You almost certainly don't need this.** As of the **2026.1.1** GA line,
YugabyteDB publishes an official *multi-arch* image with both `vector` and
`mage`, including a native `arm64` variant — so `docker compose up -d` pulls a
ready-made image and this directory is unused:

```yaml
image: yugabytedb/yugabyte:2026.1.1.1-b2   # arm64 + amd64
```

This `Dockerfile` remains as an escape hatch for building an image from a
packaged release tarball — useful for **pre-release / dev builds** that aren't
on Docker Hub yet (this demo was originally proven against the pre-GA
`2026.1.0.0-b109` tarball).

## Building from a tarball

The tarball is **not** committed to this repo (~500 MB). Place it here first.
For YugabyteDB engineers, packaged releases live in the `releases.yugabyte.com`
S3 bucket:

```bash
aws s3 cp \
  s3://releases.yugabyte.com/2026.1.1.1-b2/yugabyte-2026.1.1.1-b2-almalinux8-aarch64.tar.gz \
  db/
```

Then build, passing the filename via the required `YB_TARBALL` build arg:

```bash
docker build --platform linux/arm64 \
  --build-arg YB_TARBALL=yugabyte-2026.1.1.1-b2-almalinux8-aarch64.tar.gz \
  -t yb-graphrag:2026.1.1.1-b2 .
```

Point compose at the result with `YB_IMAGE=yb-graphrag:2026.1.1.1-b2 docker
compose up -d`.

> **Why an aarch64 tarball?** On Apple Silicon the `amd64` build crashes under
> QEMU emulation (`yb-master` `mmap: Cannot allocate memory`), so a
> QEMU-emulated image is not a workable fallback — you need a native-arch
> build. The official multi-arch image satisfies this on its own; only reach
> for a tarball when the version you need isn't published.
