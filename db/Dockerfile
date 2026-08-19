# YugabyteDB with vector + MAGE graph extensions, built from a release tarball.
#
# OPTIONAL — docker-compose.yml uses the official multi-arch
# `yugabytedb/yugabyte` image (2026.1.1 GA publishes native arm64), so this is
# only needed for pre-release / dev builds that aren't on Docker Hub. See
# db/README.md.
#
# Use a native-arch tarball: on Apple Silicon an amd64 build under QEMU
# x86-64 emulation crashes the yb-master shared-memory allocator with
# "mmap: Cannot allocate memory".
#
# YB_TARBALL is required — pass the tarball filename via --build-arg.
FROM almalinux:8

ARG YB_TARBALL
ENV YB_HOME=/home/yugabyte
WORKDIR $YB_HOME

# Fail loudly: an unset YB_TARBALL otherwise surfaces as a confusing tar error.
RUN test -n "$YB_TARBALL" || { \
      echo "ERROR: --build-arg YB_TARBALL=<tarball-in-db/> is required; see db/README.md" >&2; \
      exit 1; \
    }

# Runtime deps (mirrors the official yugabytedb/yugabyte image).
RUN dnf install -y \
      bind-utils \
      glibc-langpack-en \
      less \
      ncurses-compat-libs \
      net-tools \
      openssl \
      procps \
      python3.11 \
      which \
    && alternatives --set python3 /usr/bin/python3.11 \
    && dnf clean all && rm -rf /var/cache/yum

COPY ${YB_TARBALL} /tmp/yb.tar.gz
RUN tar xzf /tmp/yb.tar.gz -C $YB_HOME --strip-components=1 \
    && rm /tmp/yb.tar.gz \
    && $YB_HOME/bin/post_install.sh

RUN for a in ysqlsh ycqlsh yugabyted yb-admin; do \
      ln -s $YB_HOME/bin/$a /usr/local/bin/$a; \
    done

EXPOSE 5433 7000 9000 15433

# MAGE requires the ysql_yb_enable_mage gflag on both master and tserver.
CMD ["yugabyted", "start", "--daemon=false", \
     "--tserver_flags=ysql_yb_enable_mage=true", \
     "--master_flags=ysql_yb_enable_mage=true"]
