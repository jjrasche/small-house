#!/bin/sh
# Starts the factored-ui page server for this world on the Tailscale address in a detached tmux session; does nothing if it is already up.
set -eu
TREE="$HOME/workspace/factored-ui/.git-worktrees/factored-ui-house-view"
WORLD="$HOME/workspace/small-house/world.json"
ENGINE_LAUNCHER="$HOME/workspace/world-engine/kotlin/we"
BIND="$(tailscale ip -4)"
if tmux has-session -t page-8090 2>/dev/null; then echo "page-8090 already running"; exit 0; fi
tmux new-session -d -s page-8090 -c "$TREE" "java -cp 'packages/kotlin-application/build/install/kotlin-application/lib/*' ai.factoredui.application.MainKt --system $WORLD --runtime $ENGINE_LAUNCHER --bundle packages/kotlin-compose-playground/build/dist/wasmJs/productionExecutable --bind $BIND --port 8090"
echo "page-8090 started on $BIND:8090"
