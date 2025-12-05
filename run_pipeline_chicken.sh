#!/bin/bash

# simple: discover cameras -> run each in parallel -> copy results -> done

set -e

# where this project lives
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# paths to your stuff
CAMERA_EXE="$BASE_DIR/camera_project_v4l2/camera_project_v4l2"
CNN_DIR="$BASE_DIR/chicken-cnn-c/c-infer"
CNN_EXE="$CNN_DIR/pi_infer"
THERMAL_SCRIPT="$BASE_DIR/thermal_tracking.py"
THRESH=0.37

# Activate virtual environment (venv must be inside this same folder)
if [ -f "$BASE_DIR/venv/bin/activate" ]; then
    echo "[INFO] Activating virtual environment..."
    source "$BASE_DIR/venv/bin/activate"
else
    echo "[WARN] venv not found at $BASE_DIR/venv/bin/activate"
fi

# find all video devices
CAM_DEVS=($(ls /dev/video* 2>/dev/null | sort))
if [ ${#CAM_DEVS[@]} -eq 0 ]; then
    echo "[ERROR] no /dev/video* found"
    exit 1
fi

echo "[INFO] cameras found: ${CAM_DEVS[*]}"

# create one main folder for this run
RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
MAIN_DIR="$CNN_DIR/outputs/$RUN_ID"
mkdir -p "$MAIN_DIR"
echo "[INFO] main run dir: $MAIN_DIR"

# start thermal_tracking.py in parallel and log to main folder
THERM_LOG="$MAIN_DIR/thermal_log.txt"
echo "[INFO] starting thermal_tracking.py -> $THERM_LOG"
python3 "$THERMAL_SCRIPT" "$THERM_LOG" &
THERM_PID=$!
echo "[INFO] thermal_tracking.py PID: $THERM_PID"

pids=()
idx=1

for cam in "${CAM_DEVS[@]}"; do
    # per-camera folder under main dir
    outdir="$MAIN_DIR/cam$idx"
    mkdir -p "$outdir"

    # path relative to CNN_DIR for pi_infer
    rel_dir="$RUN_ID/cam$idx"

    echo "[INFO] starting pipeline for $cam -> $outdir"

    (
        # 1) capture 8 images to this camera's folder
        "$CAMERA_EXE" "$cam" "$outdir"

        # 2) run the CNN on this same folder, write result.txt into it
        (
            cd "$CNN_DIR"
            "$CNN_EXE" --dir "$rel_dir" --threshold "$THRESH" > "$outdir/result.txt"
        )

        echo "[INFO] pipeline for $cam done"
    ) &

    pids+=($!)
    idx=$((idx+1))
done

###############################################
# WAIT FOR ALL CAM PIPELINES WITH TIMEOUT (15s)
###############################################
TIMEOUT=15
start_time=$(date +%s)

echo "[INFO] Waiting up to $TIMEOUT seconds for camera pipelines..."

while :; do
    all_done=true

    for pid in "${pids[@]}"; do
        if ps -p "$pid" > /dev/null 2>&1; then
            all_done=false
        fi
    done

    # finished early
    if $all_done; then
        echo "[INFO] All camera pipelines finished early."
        break
    fi

    # timeout exceeded
    now=$(date +%s)
    elapsed=$((now - start_time))
    if [ "$elapsed" -ge "$TIMEOUT" ]; then
        echo "[WARN] Timeout reached ($TIMEOUT seconds). Killing remaining pipelines..."

        # kill only still-running ones
        for pid in "${pids[@]}"; do
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        done
        break
    fi

    sleep 0.2
done
###############################################


echo "[INFO] all camera pipelines finished"

# stop thermal_tracking.py
if ps -p "$THERM_PID" >/dev/null 2>&1; then
    echo "[INFO] stopping thermal_tracking.py"
    kill "$THERM_PID" 2>/dev/null || true
    # don't let set -e kill the script if thermal exits non-zero
    wait "$THERM_PID" 2>/dev/null || true
fi

# compute OR of results:
#   - any Status:1 in thermal_log.txt
#   - any 'UNHEALTHY' in camera result.txt files
overall="HEALTHY"

# 1) thermal OR piece stays the same
if [ -f "$THERM_LOG" ] && grep -q "Status:1" "$THERM_LOG"; then
    overall="UNHEALTHY"
fi

# 2) camera summaries: use ONLY the last 'predicted:' line from each result.txt
for cam_dir in "$MAIN_DIR"/cam*; do
    [ -d "$cam_dir" ] || continue
    res_file="$cam_dir/result.txt"
    [ -f "$res_file" ] || continue

    # get the last summary line that starts with 'predicted:'
    last_pred=$(grep '^predicted:' "$res_file" | tail -n 1)

    # if it mentions UNHEALTHY, mark overall as UNHEALTHY
    if echo "$last_pred" | grep -qi 'UNHEALTHY'; then
        overall="UNHEALTHY"
        break    # no need to keep checking once we know it's bad
    fi
done


FINAL_FILE="$MAIN_DIR/final_results.txt"
echo "FINAL_RESULT=$overall" > "$FINAL_FILE"
echo "[INFO] wrote $FINAL_FILE (FINAL_RESULT=$overall)"

echo "[INFO] Cleaning up empty camera folders..."

for cam_dir in "$MAIN_DIR"/cam*; do
    [ -d "$cam_dir" ] || continue

    # consider a camera folder “populated” if:
    #   - contains at least 1 .jpg frame
    #   - OR contains result.txt
    jpg_count=$(find "$cam_dir" -maxdepth 1 -name '*.jpg' | wc -l)
    if [ -f "$cam_dir/result.txt" ] || [ "$jpg_count" -gt 0 ]; then
        echo "[INFO] Keeping $cam_dir (populated)"
    else
        echo "[INFO] Removing empty folder: $cam_dir"
        rm -rf "$cam_dir"
    fi
done


# copy whole run folder to first USB under /media/$USER
USB_ROOT="/media/${SUDO_USER:-$USER}"
if [ -d "$USB_ROOT" ]; then
    for m in "$USB_ROOT"/*; do
        [ -d "$m" ] || continue
        dest="$m/$RUN_ID"
        cp -r "$MAIN_DIR" "$dest"
        echo "[INFO] copied $MAIN_DIR -> $dest"
        break
    done
else
    echo "[INFO] no USB under $USB_ROOT, skipping copy"
fi

echo "[INFO] all pipelines finished. Overall result: $overall"
exit 0
