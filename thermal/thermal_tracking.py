import time, sys
import numpy as np
import pygame
from scipy import interpolate
import board
import busio
import adafruit_amg88xx
import cv2
import argparse
import json

# NEW: optional output log file
parser = argparse.ArgumentParser()
parser.add_argument("out_file", nargs="?", help="optional status log file")
args = parser.parse_args()
log_file = None
if args.out_file:
    # line-buffered so kills/interrupts still flush most data
    log_file = open(args.out_file, "a", buffering=1)
    
#Import temperature configurations
with open("thermal_config.json", "r") as config_file:
    config = json.load(config_file)

cold_thres = config['cold_threshold']
hot_thres = config['hot_threshold']

#Setup I2C connection
i2c = busio.I2C(board.SCL, board.SDA)
sensor = adafruit_amg88xx.AMG88XX(i2c)

#Create pygame display
pygame.init()
WIDTH = HEIGHT = 480
lcd = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AMG8833 Thermal Camera")
lcd.fill((0, 0, 0))

#Setup color coding
COLORDEPTH = 1024
colors = []
for i in range(COLORDEPTH):
    c = pygame.color.Color(0)
    c.hsla = (int(240 - (240 * (i / COLORDEPTH))), 100, 50, 100)
    colors.append(c)

#Set up resolutions
pix_res = (8, 8)
pix_mult = 6

interp_res = (pix_res[0] * pix_mult, pix_res[1] * pix_mult)
xx = np.linspace(0, pix_res[0]-1, pix_res[0])
yy = np.linspace(0, pix_res[1]-1, pix_res[1])

grid_x = np.linspace(0, pix_res[0]-1, interp_res[0])
grid_y = np.linspace(0, pix_res[1]-1, interp_res[1])

displayPixelWidth = WIDTH / interp_res[0]
displayPixelHeight = HEIGHT / interp_res[1]

status = 0

#Intropolate function
def interp(z_var):
    f = interpolate.RectBivariateSpline(yy, xx, z_var, kx=2, ky=2)
    return f(grid_y, grid_x)
    
#Mapping function
def map_thermal_to_jpeg(x, y, interp_res=(48,38),
                        target_bl=(0,880), target_tr=(1080,0)):
							
    y =  y - 10	
    x_norm = x / (interp_res[0]-1)
    y_norm = y / (interp_res[1]-1)
    
    X_bl, Y_bl = target_bl
    X_tr, Y_tr = target_tr
    
    X_mapped = X_bl + x_norm * (X_tr - X_bl)
    Y_mapped = Y_tr + y_norm * (Y_bl - Y_tr)
    
    return int(round(X_mapped)), int(round(Y_mapped))

frame_buffer = []
AVG_FRAMES = 20

try:
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                if log_file:
                    log_file.close()
                sys.exit()

        status_int = 0
        
        #Read data
        raw = np.array(sensor.pixels)
        thermistor = sensor.temperature  

        frame_buffer.append(raw)
        if len(frame_buffer) > AVG_FRAMES:
            frame_buffer.pop(0)
        pixels = np.mean(frame_buffer, axis=0)

        #Calculate for offset
        pixels = (pixels - thermistor) * 1.12 + thermistor + 5

        bicubic = interp(pixels)
        bicubic = np.nan_to_num(bicubic, nan=0)
        bicubic = np.rot90(bicubic, k=1)
        
        #Map out hot regions
        hot_mask = (bicubic > hot_thres).astype(np.uint8)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(hot_mask, connectivity=8)
        
        hot_regions = []
        for i in range(1, num_labels):  
            x, y, w, h, area = stats[i]

            if area < 20:
                continue #Too small

            status_int = 1 #Dangerous reading

            #Map center-most temperature
            cx, cy = int(x + w // 2), int(y + h // 2)
            temp = float(bicubic[cy, cx])  

            hot_regions.append((x,y,w,h,temp))
            
        #Map out cold regions
        cold_mask = (bicubic < cold_thres).astype(np.uint8)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cold_mask, connectivity=8)

        cold_regions = []
        for i in range(1, num_labels):
            x, y, w, h, area = stats[i]

            if area < 20:
                continue #Too small
                
            #Map center-most temperature
            cx, cy = int(x + w // 2), int(y + w // 2)
            temp = float(bicubic[cy, cx])  

            status_int = 1 #Dangerous reading

            cold_regions.append((x,y,w,h,temp))
        
        #Find median temperature
        h, w = bicubic.shape
        sample_coords = [
            (0, 0),         
            (w//2, 0),        
            (w-1, 0),     

            (0, h//2),    
            (w//2, h//2),    
            (w-1, h//2),        

            (0, h-1),    
            (w//2, h-1),                
            (w-1, h-1)                  
        ]
        samples = [bicubic[y, x] for (x, y) in sample_coords]
        median_norm = np.median(samples)

        #Map out non-dangerous chickens
        normal_mask = ((bicubic > cold_thres) & (bicubic < hot_thres) & (np.abs(bicubic - median_norm) > 2.0)).astype(np.uint8)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(normal_mask, connectivity=8)
        
        normal_regions = []
        for i in range(1, num_labels):
            x, y, w, h, area = stats[i]

            if area < 20:
                continue #Too small
                
            #Map center-most temperature
            cx, cy = int(x + w // 2), int(y + h // 2)
            temp = float(bicubic[cy, cx])
                
            normal_regions.append((x, y, w, h, temp))
          
        display_bicubic = np.rot90(bicubic, k=-1)
        display_bicubic = np.flipud(display_bicubic)
        
        #Filter to remove normal square if hold or cold inside
        filtered_normal = []

        for (nx, ny, nw, nh, nt) in normal_regions:
            nx1, ny1 = nx, ny
            nx2, ny2 = nx + nw, ny + nh

            overlaps_hot = False
            overlaps_cold = False

            #Check all hot regions
            for (hx, hy, hw, hh, ht) in hot_regions:
                hx1, hy1 = hx, hy
                hx2, hy2 = hx + hw, hy + hh

                inter_w = max(0, min(nx2, hx2) - max(nx1, hx1))
                inter_h = max(0, min(ny2, hy2) - max(ny1, hy1))
                inter_area = inter_w * inter_h

                if inter_area > 0:
                    overlaps_hot = True
                    break
                    
            #Check all cold regions
            for (hx, hy, hw, hh, ht) in cold_regions:
                hx1, hy1 = hx, hy
                hx2, hy2 = hx + hw, hy + hh

                inter_w = max(0, min(nx2, hx2) - max(nx1, hx1))
                inter_h = max(0, min(ny2, hy2) - max(ny1, hy1))
                inter_area = inter_w * inter_h

                if inter_area > 0:
                    overlaps_cold = True
                    break                        
            
            if not (overlaps_hot or overlaps_cold):
                filtered_normal.append((nx, ny, nw, nh, nt)) #No hot or cold region inside

        #Replace original
        normal_regions = filtered_normal
        
        #Normaize temperatures
        min_temp, max_temp = np.min(pixels), np.max(pixels)
        norm_pixels = ((display_bicubic - min_temp) / (max_temp - min_temp)) * (COLORDEPTH - 1)
        norm_pixels = np.clip(norm_pixels, 0, COLORDEPTH - 1).astype(int)

        lcd.fill((0, 0, 0))
        
        #Draw thermal image
        for ix, row in enumerate(norm_pixels):
            for jx, val in enumerate(row):
                color = colors[val]
                pygame.draw.rect(
                    lcd, color,
                    (displayPixelWidth * ix, displayPixelHeight * jx,
                     displayPixelWidth, displayPixelHeight)
                )

        font = pygame.font.SysFont("Arial", 18)

        #Draw hot squares
        for (x, y, w, h, temp) in hot_regions:
            color = (255, 0, 0)
            
            flipped_x = (interp_res[0] - (x + w)) * displayPixelWidth
            flipped_y = (interp_res[1] - (y + h)) * displayPixelHeight

            pygame.draw.rect(
                lcd, color,
                (flipped_x, flipped_y,
                w * displayPixelWidth, h * displayPixelHeight), 2)
            
            label = f"{temp:.1f}°C"
            text_surface = font.render(label, True, color)
            lcd.blit(text_surface, (flipped_x, flipped_y - 20))
            
        #Draw cold squares
        for (x, y, w, h, temp) in cold_regions:
            color = (0, 0, 255)
            
            flipped_x = (interp_res[0] - (x + w)) * displayPixelWidth
            flipped_y = (interp_res[1] - (y + h)) * displayPixelHeight
            
            pygame.draw.rect(
                lcd, color,
                (flipped_x, flipped_y,
                w * displayPixelWidth, h * displayPixelHeight), 2)
            
            label = f"{temp:.1f}°C"
            text_surface = font.render(label, True, color)
            lcd.blit(text_surface, (flipped_x, flipped_y - 20))
            
        #Draw normal squares
        for (x, y, w, h, temp) in normal_regions:
            color = (255, 255, 255)  

            flipped_x = (interp_res[0] - (x + w)) * displayPixelWidth
            flipped_y = (interp_res[1] - (y + h)) * displayPixelHeight

            pygame.draw.rect(
                lcd, color,
                (flipped_x, flipped_y,
                 w * displayPixelWidth, h * displayPixelHeight), 2)

            label = f"{temp:.1f}°C"
            text_surface = font.render(label, True, color)
            lcd.blit(text_surface, (flipped_x, flipped_y - 20))

        font = pygame.font.SysFont("Arial", 24)
        text = font.render(
            f"Ambient: {thermistor:.2f}°C",
            True, (255, 255, 255)
        )
        lcd.blit(text, (10, 10))
        
        #Check ambient temperature
        if thermistor > 30:
            status_int = 1

        pygame.display.update()

        #Display status
        status = status_int
        line = f"Status:{status}"        
        if status:
            print(line)
            
        mapped_rectangles = []

        for rect in hot_regions + cold_regions + normal_regions:
            x, y, w, h, temp = rect
            x = interp_res[0] - (x + w)
            y = interp_res[1] - (y + h)
            
            if y < 10:
                continue #Out of vertical range
             
            bl_x, bl_y = x, y + h
            tr_x, tr_y = x + w, y
			
            bl = map_thermal_to_jpeg(bl_x, bl_y)
            tr = map_thermal_to_jpeg(tr_x, tr_y)
            mapped_rectangles.append([bl, tr])

        if mapped_rectangles:
            print(mapped_rectangles)

        # NEW: log to file if requested
        if log_file:
            ts = time.time()
            log_file.write(f"{ts},{line}\n")
        
        time.sleep(0.1)

except KeyboardInterrupt:
    pygame.quit()
    if log_file:
        log_file.close()
    sys.exit()
