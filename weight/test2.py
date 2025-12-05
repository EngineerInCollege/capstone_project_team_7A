#!/usr/bin/env python3
import time, sys, statistics, argparse
import RPi.GPIO as GPIO

# === Wiring (BCM) ===
DOUT = 5   # HX711 DOUT -> Raspberry Pi GPIO 5
SCK  = 6   # HX711 SCK  -> Raspberry Pi GPIO 6

# === Timing ===
CLK_DELAY = 2e-6   # 2 µs; safe, but fast enough
READY_TIMEOUT = 0.5  # seconds to wait for DOUT to go LOW

def gpio_setup():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SCK, GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(DOUT, GPIO.IN)

def gpio_cleanup():
    GPIO.output(SCK, GPIO.LOW)
    GPIO.cleanup()

def _pulse():
    GPIO.output(SCK, True)
    # minimal hold
    time.sleep(CLK_DELAY)
    GPIO.output(SCK, False)
    time.sleep(CLK_DELAY)

def is_ready():
    """HX711 ready when DOUT is LOW."""
    return GPIO.input(DOUT) == 0

def wait_ready(timeout=READY_TIMEOUT):
    t0 = time.time()
    while not is_ready():
        if time.time() - t0 > timeout:
            return False
        time.sleep(0.0002)
    return True

def read_raw_24():
    """
    Read one 24-bit two's complement sample (A, gain=128).
    Returns int or raises TimeoutError.
    """
    if not wait_ready():
        raise TimeoutError("DOUT stayed HIGH (no data ready).")

    val = 0
    # 24 clock cycles, MSB first. Sample DOUT while SCK is HIGH.
    for _ in range(24):
        GPIO.output(SCK, True)
        time.sleep(CLK_DELAY)
        bit = GPIO.input(DOUT) & 1
        val = (val << 1) | bit
        GPIO.output(SCK, False)
        time.sleep(CLK_DELAY)

    # 25th pulse to select channel A, gain 128
    _pulse()

    # sign-extend 24-bit two's complement
    if val & 0x800000:
        val -= 1 << 24
    return val

def read_mean(n=6, trim=0):
    vals = []
    for _ in range(n):
        vals.append(read_raw_24())
    vals.sort()
    if trim > 0 and len(vals) > 2*trim:
        vals = vals[trim:-trim]
    return statistics.fmean(vals)

def power_cycle():
    """Optional: power-down then wake to re-sync."""
    GPIO.output(SCK, True)
    time.sleep(0.07)
    GPIO.output(SCK, False)
    time.sleep(0.07)

def quick_gpio_probe(samples=20):
    """
    Probe DOUT level while pulsing SCK to see if anything changes.
    Returns dict with level stats and transition flags.
    """
    highs = lows = transitions = 0
    last = GPIO.input(DOUT)
    for _ in range(samples):
        # idle sample
        cur = GPIO.input(DOUT)
        if cur != last:
            transitions += 1
        last = cur
        highs += 1 if cur else 0
        lows  += 0 if cur else 1
        # generate a few pulses; HX711 ignores clocks when not ready,
        # but if wired wrong we might still see line-level changes
        for __ in range(3):
            _pulse()
    return {
        "highs": highs,
        "lows": lows,
        "transitions": transitions,
        "ready_now": is_ready()
    }

def main():
    ap = argparse.ArgumentParser(description="HX711 terminal reader with diagnostics (GPIO5=DOUT, GPIO6=SCK).")
    ap.add_argument("--samples", type=int, default=6, help="Averaging per print.")
    ap.add_argument("--trim", type=int, default=0, help="Outlier trim per side.")
    ap.add_argument("--interval", type=float, default=0.1, help="Print interval seconds (0.1 => ~10 Hz).")
    ap.add_argument("--scale", type=float, default=1.0, help="Counts per unit (set after calibration).")
    ap.add_argument("--unit", default="g", help="Unit label.")
    ap.add_argument("--debug", action="store_true", help="Print diagnostics on abnormal reads.")
    args = ap.parse_args()

    gpio_setup()
    zero = 0.0
    scale = float(args.scale)

    try:
        power_cycle()

        # Startup probe
        probe = quick_gpio_probe()
        print(f"[Probe] ready={probe['ready_now']} highs={probe['highs']} lows={probe['lows']} transitions={probe['transitions']}")

        # Tare
        print("Taring... remove all weight.")
        time.sleep(0.5)
        zero = read_mean(n=max(args.samples, 8), trim=min(args.trim, 2))
        print(f"Zero offset: {zero:.2f} counts")

        # Optional one-shot calibration (if no scale supplied)
        if abs(scale - 1.0) < 1e-9:
            print("\nOptional calibration: place known weight, press Enter (or Ctrl+C to skip)...")
            try:
                input()
                reading = read_mean(n=args.samples, trim=args.trim)
                known = float(input(f"Enter known weight ({args.unit}): ").strip())
                if abs(known) > 1e-12:
                    scale = (reading - zero) / known
                    print(f"Calibrated scale: {scale:.6f} counts/{args.unit}")
                else:
                    print("Skipped calibration (known==0).")
            except KeyboardInterrupt:
                print("\nCalibration skipped.")

        print("\nReading... (Ctrl+C to stop)")
        consec_allones = 0
        consec_timeouts = 0

        while True:
            try:
                avg = read_mean(n=args.samples, trim=args.trim)
                consec_timeouts = 0
                # Detect special patterns
                if avg == -1.0:
                    consec_allones += 1
                else:
                    consec_allones = 0

                units = (avg - zero) / (scale if scale != 0 else 1.0)
                sys.stdout.write(f"\rWeight: {units:9.2f}{args.unit}   (raw:{avg:10.2f})")
                sys.stdout.flush()

                # Health line (prints only when abnormal)
                if args.debug and (consec_allones >= 3):
                    probe = quick_gpio_probe()
                    sys.stdout.write(
                        f"\n[DIAG] Repeated -1 (all 1s). "
                        f"ready={probe['ready_now']} highs={probe['highs']} lows={probe['lows']} trans={probe['transitions']}. "
                        f"Check VCC=3.3V, GND, DT->GPIO5, SCK->GPIO6.\n"
                    )
                time.sleep(args.interval)

            except TimeoutError:
                consec_timeouts += 1
                if args.debug or consec_timeouts % 5 == 1:
                    sys.stdout.write(
                        f"\n[DIAG] Timeout waiting for ready. DOUT stuck HIGH? "
                        f"(check power 3.3V, GND, wiring, load cell connected)\n"
                    )
                time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nExit.")
                break

    finally:
        gpio_cleanup()

if __name__ == "__main__":
    main()
