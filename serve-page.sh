#!/bin/sh
# Starts the factored-ui page server for this world: a systemd user service (page-8090) that restarts itself and survives logouts (linger is on).
set -eu
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
systemctl --user enable --now page-8090.service
systemctl --user is-active page-8090.service
