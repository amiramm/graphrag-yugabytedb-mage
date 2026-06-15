# YugabyteDB (master / 2026.1 line) with vector + MAGE graph extensions.
#
# Built from a native aarch64 AlmaLinux 8 release tarball so it runs at full
# speed on Apple Silicon (no QEMU x86-64 emulation, which crashes the
# yb-master shared-memory allocator with "mmap: Cannot allocate memory").
#
# Pass the tarball name in via build-arg; default is the build this demo was
# proven against.
FROM almalinux:8

ARG YB_TARBALL=yugabyte-2026.1.0.0-b109-almalinux8-aarch64.tar.gz
ENV YB_HOME=/home/yugabyte
WORKDIR $YB_HOME

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
