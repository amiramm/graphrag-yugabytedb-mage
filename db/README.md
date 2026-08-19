# Build the database image yourself (optional)

You don't need this to run the demo. `docker compose up -d` pulls an official
image that already includes the `vector` and `mage` extensions, and the 2026.1.1
tags cover both `arm64` and `amd64`:

```yaml
image: yugabytedb/yugabyte:2026.1.1.1-b2
```

Use the `Dockerfile` here only when you want a version that isn't on Docker Hub
yet — a newer build, or one you compiled yourself. It builds an image from a
YugabyteDB release tarball.

## Build from a release tarball

The tarball is about 500 MB, so it isn't part of this repository. Put it in the
`db` directory, because that directory is the build context that the
Dockerfile's `COPY ${YB_TARBALL}` reads from.

Run both commands from the repository root, and use the tarball that matches
your machine: `aarch64` on Apple Silicon, `x86_64` on Intel and AMD. You can
find every build on the
[YugabyteDB downloads page](https://download.yugabyte.com/). Set the
architecture once and both commands follow it:

```sh
ARCH=aarch64   # or x86_64
TARBALL=yugabyte-2026.1.1.1-b2-el8-$ARCH.tar.gz

curl -Lo db/$TARBALL \
  https://software.yugabyte.com/releases/2026.1.1.1/$TARBALL
```

Then build the image. Pass the filename in `YB_TARBALL`, and note that `-f`
points at the Dockerfile while the last argument (`db`) sets the build context.
Don't pass `--platform`: Docker builds for your own architecture, which is what
you want, and the base image is available for both:

```sh
docker build \
  -f db/Dockerfile \
  --build-arg YB_TARBALL=$TARBALL \
  -t yb-graphrag:2026.1.1.1-b2 \
  db
```

Finally, point compose at the image you built:

```sh
YB_IMAGE=yb-graphrag:2026.1.1.1-b2 docker compose up -d
```

> **Match the tarball to your machine.** On Apple Silicon, use an `aarch64`
> build. An `amd64` build running under QEMU x86-64 emulation fails to start:
> `yb-master` reports `mmap: Cannot allocate memory`, however much memory you
> give the virtual machine.
