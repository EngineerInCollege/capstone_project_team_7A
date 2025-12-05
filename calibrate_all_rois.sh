#!/bin/bash

# Calibrate ROI for each connected camera:
#  - discover /dev/video* devices
#  - capture sample images from all cameras in parallel (with timeout)
#  - run calibrate_roi.py on one image per camera (sequential, interactive)
#  - copy resulting roi_camX.json into duck-cnn-c/roi

set -e

# where this project lives (same style as run_pipeline.sh)
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# paths to your stuff
CAMERA_EXE="$BASE_DIR/camera_project_v4l2/camera_project_v4l2"
CALIB_SCRIPT="$BASE_DIR/duck-cnn-c/scripts/calibrate_roi.py"
ROI_ROOT="$BASE_DIR/duck-cnn-c/roi"

# Activate virtual environment (venv must be inside this same folder)
if [ -f "$BASE_DIR/venv/bin/activate" ]; then
    echo "[INFO] Activating virtual environment..."
    # shellcheck disable=SC1090
    source "$BASE_DIR/venv/bin/activate"
else
    echo "[WARN] venv not found at $BASE_DIR/venv/bin/activate (continuing without venv)"
fi

# sanity checks
if [ ! -x "$CAMERA_EXE" ]; then
    echo "[ERROR] CAMERA_EXE not found or not executable: $CAMERA_EXE"
    exit 1
fi

if [ ! -f "$CALIB_SCRIPT" ]; then
    echo "[ERROR] calibrate_roi.py not found at: $CALIB_SCRIPT"
    exit 1
fi

# find all video devices (same approach as run_pipeline.sh)
CAM_DEVS=($(ls /dev/video* 2>/dev/null | sort || true))
if [ ${#CAM_DEVS[@]} -eq 0 ]; then
    echo "[ERROR] no /dev/video* found"
    exit 1
fi

echo "[INFO] cameras found: ${CAM_DEVS[*]}"

# create a calibration run directory (similar to c-infer/run-...)
CALIB_RUN_ID="calib-$(date +%Y%m%d-%H%M%S)"
CALIB_MAIN="$BASE_DIR/calibration_runs/$CALIB_RUN_ID"
mkdir -p "$CALIB_MAIN"
echo "[INFO] calibration run dir: $CALIB_MAIN"

# ensure ROI_ROOT exists
mkdir -p "$ROI_ROOT"
echo "[INFO] global ROI directory: $ROI_ROOT"

#######################################
# STAGE 1: PARALLEL CAPTURE PER CAMERA
#######################################
echo
echo "[INFO] Starting parallel capture from all cameras..."

pids=()
idx=1
for cam in "${CAM_DEVS[@]}"; do
    cam_name="cam$idx"
    cam_dir="$CALIB_MAIN/$cam_name"
    LIVE_DIR="$cam_dir/live"
    mkdir -p "$LIVE_DIR"

    echo "[INFO] Scheduling capture for $cam_name ($cam) -> $LIVE_DIR"

    (
        echo "[INFO] [${cam_name}] Capturing sample images from $cam into $LIVE_DIR ..."
        # timeout so bogus devices (e.g. /dev/video1) don't hang forever
        if ! timeout 8 "$CAMERA_EXE" "$cam" "$LIVE_DIR"; then
            echo "[WARN] [${cam_name}] Capture failed or timed out for $cam (likely not a usable camera)."
            # mark failure for this cam
            echo "FAIL" > "$cam_dir/capture_failed"
        fi
    ) &

    pids+=($!)
    idx=$((idx+1))
done

TIMEOUT=3
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
echo "[INFO] Parallel capture stage complete."

###########################################
# STAGE 2: SEQUENTIAL CALIBRATION PER CAM
###########################################
echo
echo "[INFO] Starting sequential ROI calibration per camera..."

idx=1
for cam in "${CAM_DEVS[@]}"; do
    cam_name="cam$idx"
    cam_dir="$CALIB_MAIN/$cam_name"
    LIVE_DIR="$cam_dir/live"

    echo
    echo "==========================================="
    echo "[INFO] Calibrating ROI for $cam_name ($cam)"
    echo "  - Capture dir: $LIVE_DIR"
    echo "==========================================="

    # skip cameras that failed capture
    if [ -f "$cam_dir/capture_failed" ]; then
        echo "[WARN] [${cam_name}] Skipping calibration (capture_failed flag present)."
        idx=$((idx+1))
        continue
    fi

    # pick one sample image from LIVE_DIR
    sample_img="$(find "$LIVE_DIR" -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) | sort | head -n 1 || true)"

    if [ -z "$sample_img" ]; then
        echo "[WARN] [${cam_name}] No images captured in $LIVE_DIR; skipping this camera."
        idx=$((idx+1))
        continue
    fi

    echo "[INFO] [${cam_name}] Using sample image for calibration: $sample_img"

    cam_roi_tmp="$cam_dir/roi_${cam_name}.json"

    echo "[INFO] [${cam_name}] Launching ROI calibration."
    echo "       A window will open. Click 4 points around the SCALE area."
    echo "       Press 'r' to reset if needed, 'q' or ESC to finish."
    echo

    python3 "$CALIB_SCRIPT" \
        --image "$sample_img" \
        --out "$cam_roi_tmp"

    if [ ! -f "$cam_roi_tmp" ]; then
        echo "[WARN] [${cam_name}] No ROI file generated (maybe you quit early). Skipping copy."
        idx=$((idx+1))
        continue
    fi

    final_roi="$ROI_ROOT/roi_${cam_name}.json"
    cp "$cam_roi_tmp" "$final_roi"

    echo "[INFO] [${cam_name}] Saved ROI to: $final_roi"
    idx=$((idx+1))
done

echo
echo "[INFO] Calibration complete."
echo "[INFO] ROIs now available in: $ROI_ROOT"
echo "[INFO] You can now run your main pipeline; cropping_live.py will use these ROIs."
