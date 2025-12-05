import RPi.GPIO as GPIO
import time

# Use BCM pin numbering
GPIO.setmode(GPIO.BCM)

# Set pins 5 and 6 as inputs
GPIO.setup(5, GPIO.IN)
GPIO.setup(6, GPIO.IN)

try:
    while True:
        pin5_value = GPIO.input(5)
        pin6_value = GPIO.input(6)
        print(f"Pin 5: {pin5_value}, Pin 6: {pin6_value}")
        time.sleep(0.1)  # Adjust speed if needed
except KeyboardInterrupt:
    print("Stopping program...")
finally:
    GPIO.cleanup()
