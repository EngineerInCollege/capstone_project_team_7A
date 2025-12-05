import time
import RPi.GPIO as GPIO  # import GPIO

'''
from hx711 import HX711  # import the class HX711

try:
	hx711 = HX711(
	dout_pin = 5,
	pd_sck_pin = 6,
	channel='A',
	gain=64
)
'''

DT = 5
SCK = 6

GPIO.setmode(GPIO.BCM)
GPIO.setup(DT, GPIO.IN)
GPIO.setup(SCK, GPIO.OUT)

print('Starting HX711')

try:
	while True:
		dt_state = GPIO.input(DT)
		print('DT', dt_state)
		time.sleep(0.05)
except KeyboardInterrupt:
	print('Exiting')
finally:
	GPIO.cleanup()

'''
hx711.reset()
measures = hx711.get_raw_data_mean(num_measures=3)

finally:
	GPIO.cleanup()
	
print("...".join(measures))


DT_PIN = 5
SCK_PIN = 6

hx = HX711(dout_pin=DT_PIN, pd_sck_pin=SCK_PIN)
 #hx.set_reading_format("MSB", "MSB")
hx.reset()
hx.tare()

print("Taring done. Place weight on the scale.")

while True:
	try:
		val =hx.get_weight_mean(10)
		print(f"Raw Value: {val}")
		time.sleep(1)
	except (KeyboardInterrupt, SystemExit):
		print("Cleanig up")
		hx.power_down()
		hx.power_up()
		break
'''
