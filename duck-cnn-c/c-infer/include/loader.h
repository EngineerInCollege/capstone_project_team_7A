#pragma once
#include "tinycnn.h"

// load c1.bin/c2.bin/c3.bin and fc.bin (FP32, little-endian)
int load_conv_from_bin(const char *path, Conv2D *L, int inC, int outC, int k);
int load_fc_from_bin(const char *path, float w32[32], float *b);
