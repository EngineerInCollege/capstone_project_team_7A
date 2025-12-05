#!/bin/bash

# simple: discover cameras -> run each in parallel -> copy results -> done

set -e

# where this project lives
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# paths to your stuff
CAMERA_EXE="$BASE_DIR/camera_project_v4l2/camera_project_v4l2"
CNN_DIR="$BASE_DIR/duck-cnn-c/c-infer"
CNN_EXE="$CNN_DIR/pi_infer"	
THERMAL_DIR="$BASE_DIR/thermal"
THERMAL_SCRIPT="$THERMAL_DIR/thermal_tracking.py"
PY_CNN_SCRIPT="$BASE_DIR/duck-cnn-c/scripts/infer_folder.py"
CROPPING_SCRIPT="$BASE_DIR/duck-cnn-c/scripts/cropping_live.py"
ROI_ROOT="$BASE_DIR/duck-cnn-c/roi"
THRESH=0.3

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
cd "$THERMAL_DIR"
THERM_LOG="$MAIN_DIR/thermal_log.txt"
echo "[INFO] starting thermal_tracking.py -> $THERM_LOG"
python3 "$THERMAL_SCRIPT" "$THERM_LOG" &
THERM_PID=$!
echo "[INFO] thermal_tracking.py PID: $THERM_PID"
cd "$BASE_DIR"

pids=()
idx=1

for cam in "${CAM_DEVS[@]}"; do
    # per-camera folder under main dir
    outdir="$MAIN_DIR/cam$idx"
    mkdir -p "$outdir"

    LIVE_DIR="$outdir/live"
    CROPPED_DIR="$outdir/cropped"
    LAST5_DIR="$outdir/cropped_last5"
    mkdir -p "$LIVE_DIR" "$CROPPED_DIR" "$LAST5_DIR"

    # path relative to CNN_DIR for pi_infer
    rel_dir="$RUN_ID/cam$idx"

    echo "[INFO] starting pipeline for $cam -> $outdir"

    (
        # 1) capture 8 images to this camera's folder
        "$CAMERA_EXE" "$cam" "$LIVE_DIR"

        # 2) run the CNN on this same folder, write result.txt into it
       if [ -f "$CROPPING_SCRIPT" ]; then
			echo "[INFO] Cropping ducks for $cam using ROI_ROOT=$ROI_ROOT"
            python3 "$CROPPING_SCRIPT" \
				--src_root "$LIVE_DIR" \
				--dst_root "$CROPPED_DIR" \
				--resize_to 128 \
				--roi_root "$ROI_ROOT"
        else
            echo "[WARN] Cropping script not found at $CROPPING_SCRIPT; skipping cropping for $cam"
        fi

                # All crops (center-crops + duck crops)
        mapfile -t CROPPED_FILES < <(find "$CROPPED_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' \) | sort)

        if [ "${#CROPPED_FILES[@]}" -eq 0 ]; then
            echo "[WARN] No cropped images found for $cam; writing empty result.txt"
            echo "[WARN] No cropped images for this camera" > "$outdir/result.txt"
        else
            # Filter to only *duck-labeled* crops (with color suffix)
            # Our cropping script names real duck crops like:
            #   frame_0003_1_pink.jpg
            #   frame_0004_2_yellow.jpg
            # and fallback center crops like:
            #   frame_0003.jpg  (no color / no extra suffix)
            DUCK_FILES=()
            for f in "${CROPPED_FILES[@]}"; do
                base=$(basename "$f")
                if [[ "$base" =~ _(pink|green|yellow|orange)\.[Jj][Pp][Ee]?[Gg]$ ]]; then
                    DUCK_FILES+=("$f")
                fi
            done

            if [ "${#DUCK_FILES[@]}" -eq 0 ]; then
                # No color-labeled crops at all:
                #   - either no duck was present
                #   - or ROI was bad and only center-crops were produced
                # In this case, we DO NOT run the CNN and we DO NOT
                # contribute this camera to the final HEALTHY/UNHEALTHY result
                echo "[WARN] No duck-labeled crops found for $cam; assuming no duck or bad ROI."
                echo "NO_DUCK_FOUND" > "$outdir/result.txt"
            else
                # copy last up to 5 *duck* images into LAST5_DIR
                total="${#DUCK_FILES[@]}"
                start=0
                if [ "$total" -gt 5 ]; then
                    start=$((total - 5))
                fi

                # ensure LAST5_DIR is empty first
                rm -f "$LAST5_DIR"/* 2>/dev/null || true

                for ((i=start; i<total; i++)); do
                    src="${DUCK_FILES[i]}"
                    cp "$src" "$LAST5_DIR"/
                done

                echo "[INFO] Running Python CNN on last $((total - start)) duck crops for $cam"

                if [ -f "$PY_CNN_SCRIPT" ]; then
                    (
                        cd "$(dirname "$PY_CNN_SCRIPT")"
                        # infer_folder.py takes a path to a folder or single image
                        python3 "$(basename "$PY_CNN_SCRIPT")" "$LAST5_DIR" \
                            --threshold "$THRESH" > "$outdir/result.txt"
                    ) || echo "[WARN] Python CNN failed for $cam"
                else
                    echo "[ERROR] Python CNN script not found at $PY_CNN_SCRIPT"
                    echo "[ERROR] Python CNN script missing" > "$outdir/result.txt"
                fi
            fi
        fi

        echo "[INFO] pipeline for $cam done"

    ) &

    pids+=($!)
    idx=$((idx+1))
done

###############################################
# WAIT FOR ALL CAM PIPELINES WITH TIMEOUT
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

NO_DUCK_COUNT=0
TOTAL_CAMERAS=0

# 1) thermal OR piece stays the same
if [ -f "$THERM_LOG" ] && grep -q "Status:1" "$THERM_LOG"; then
    overall="UNHEALTHY"
fi

# 2) camera summaries
for cam_dir in "$MAIN_DIR"/cam*; do
    [ -d "$cam_dir" ] || continue

    res_file="$cam_dir/result.txt"
    [ -f "$res_file" ] || continue
    
    if [ "$res_file" ]; then
		TOTAL_CAMERAS=$((TOTAL_CAMERAS+1))
	fi

    # If the camera said "NO_DUCK_FOUND", count it
    if grep -q "NO_DUCK_FOUND" "$res_file"; then
        NO_DUCK_COUNT=$((NO_DUCK_COUNT+1))
        continue
    fi

    # Cameras with no predictions (no duck or corrupted) are ignored
    summary=$(grep '^predicted:' "$res_file" | tail -n 1)
    [ -n "$summary" ] || continue

    u_count=$(echo "$summary" | sed -E 's/.*UNHEALTHY=([0-9]+).*/\1/')
    h_count=$(echo "$summary" | sed -E 's/.*HEALTHY=([0-9]+).*/\1/')

    echo "UNHEALTHY=$u_count HEALTHY=$h_count"

    # if unhealthy >= healthy, mark overall unhealthy
    if [ "$u_count" -ge "$h_count" ]; then
        overall="UNHEALTHY"
        break
    fi
done

# 3) NEW RULE:
# If *every* camera reported NO_DUCK_FOUND override everything
if [ "$TOTAL_CAMERAS" -gt 0 ] && [ "$NO_DUCK_COUNT" -eq "$TOTAL_CAMERAS" ]; then
    echo "[INFO] All cameras reported NO_DUCK_FOUND — overriding final result."
    overall="NO_DUCK_DETECTED"
fi

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
