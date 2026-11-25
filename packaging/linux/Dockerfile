# glibc build environment for the Linux release. Ubuntu 22.04 (glibc 2.35) so the
# binary also runs on older distros; the digest pins the image for reproducible builds.
FROM ubuntu:22.04@sha256:b000e69a50ff940390233025e7a337fb8469b509e2334fa4d018ac30f3e18cdb

# SDL3 is fetched and linked statically; its audio/video backends need these headers
# at build time and load the libraries at runtime (dlopen).
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential cmake ninja-build pkg-config git ca-certificates python3 zip file \
        libasound2-dev libpulse-dev libpipewire-0.3-dev libjack-dev libsndio-dev \
        libx11-dev libxext-dev libxrandr-dev libxcursor-dev libxi-dev libxss-dev libxfixes-dev libxtst-dev \
        libxkbcommon-dev libwayland-dev wayland-protocols libdecor-0-dev \
        libegl-dev libgl-dev libgles-dev libdrm-dev libgbm-dev \
        libdbus-1-dev libudev-dev libibus-1.0-dev \
    && rm -rf /var/lib/apt/lists/*
