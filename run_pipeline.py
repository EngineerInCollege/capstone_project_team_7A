
import subprocess
import time
import RPi.GPIO as GPIO
from pathlib import Path

LED_PIN = 27
GPIO.setmode(GPIO.BCM)
GPIO.setup(LED_PIN, GPIO.OUT)

BASE_DIR = Path(__file__).resolve().parent
PIPELINE_SH = BASE_DIR / "run_pipeline.sh"

try:
	GPIO.output(LED_PIN, 1)
	time.sleep(2)
	
	subprocess.run(["bash", str(PIPELINE_SH)])
	
	time.sleep(2)
	GPIO.output(LED_PIN, 0)
	
finally:
	GPIO.cleanup()
