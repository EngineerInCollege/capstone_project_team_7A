#pragma once
#include <stdint.h>

// File path version (for testing)
float *load_rgb_normalized_128(const char *image_path); // returns float[128*128], free() when done

// Direct-from-camera (RGB or BGR) → grayscale normalized [-1,1]
void preprocess_from_rgb888(const uint8_t *rgb, int w, int h, int stride, float out128[128*128]);
void preprocess_from_bgr888(const uint8_t *bgr, int w, int h, int stride, float out128[128*128]);
