#pragma once
#include <stddef.h>

typedef struct {
    int C, H, W;
    float *data;   // size C*H*W
} Tensor;

typedef struct {
    int inC, outC, k; // k=3
    float *w;         // [outC][inC][k][k] OIHW
    float *b;         // [outC]
} Conv2D;

// Net weights container (FP32)
typedef struct {
    Conv2D c1, c2, c3;
    float  fc_w[32];
    float  fc_b;
} TinyConvNet;

// forward
void conv3x3_s1p1_forward(const Tensor *x, const Conv2D *L, Tensor *y);
void relu_inplace(Tensor *x);
void maxpool2x2_forward(const Tensor *x, Tensor *y);
void global_avg_pool_forward(const Tensor *x, float out[32]);
float fc_forward(const float *x32, const float *W32, float b);
float sigmoidf(float z);

// end-to-end forward (returns probability of UNHEALTHY)
float tiny_forward_prob(const TinyConvNet *net, const Tensor *input_1x128x128);

// housekeeping
void init_conv(Conv2D *L, int inC, int outC, int k);
void free_conv(Conv2D *L);
