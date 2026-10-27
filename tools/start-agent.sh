#!/bin/sh
# Starts the seedbox agent in the background, unless it is already running.
cd "$(dirname "$0")" || exit 1
PID_FILE="$HOME/.tlex-upload/agent.pid"
pid=$(cat "$PID_FILE" 2>/dev/null)
# The pid's command line, not just a live pid: after a restart the number may be another's
if [ -n "$pid" ] && grep -qs seedbox_agent "/proc/$pid/cmdline"; then
    echo "The agent is already running (pid $pid)"
    exit 0
fi
nohup python3 seedbox_agent.py run >> "$HOME/.tlex-upload/agent.log" 2>&1 &
echo $! > "$PID_FILE"
echo "The agent is running (pid $!), log in ~/.tlex-upload/agent.log"
