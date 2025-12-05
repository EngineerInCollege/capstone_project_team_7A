#include "tinycnn.h"

#include <stdlib.h>
#include <math.h>
#include <string.h>

// --------- Convolution layer helpers ---------

void init_conv(Conv2D *L, int inC, int outC, int k) {
    L->inC = inC;
    L->outC = outC;
    L->k = k;
    size_t wcount = (size_t)outC * inC * k * k;
    L->w = (float *)malloc(wcount * sizeof(float));
    L->b = (float *)malloc(outC * sizeof(float));
}

void free_conv(Conv2D *L) {
    if (L->w) free(L->w);
    if (L->b) free(L->b);
    L->w = NULL;
    L->b = NULL;
    L->inC = L->outC = L->k = 0;
}

void conv3x3_s1p1_forward(const Tensor *x, const Conv2D *L, Tensor *y) {
    const int C  = x->C;
    const int H  = x->H;
    const int W  = x->W;
    const int OC = L->outC;
    const int IC = L->inC;
    const int K  = 3;
    const int P  = 1;

    // We expect C == IC
    (void)C; // silence unused warning if different, but we rely on IC for loops

    for (int oc = 0; oc < OC; ++oc) {
        for (int h = 0; h < H; ++h) {
            for (int w = 0; w < W; ++w) {
                float sum = L->b[oc];
                for (int ic = 0; ic < IC; ++ic) {
                    const float *Xin  = x->data + ic * H * W;
                    const float *Kern = L->w + (((oc * IC) + ic) * K * K);

                    for (int kh = 0; kh < K; ++kh) {
                        int ih = h + kh - P;
                        if ((unsigned)ih >= (unsigned)H) continue;
                        for (int kw = 0; kw < K; ++kw) {
                            int iw = w + kw - P;
                            if ((unsigned)iw >= (unsigned)W) continue;
                            sum += Xin[ih * W + iw] * Kern[kh * K + kw];
                        }
                    }
                }
                y->data[oc * H * W + h * W + w] = sum;
            }
        }
    }
}

// --------- Activations & pooling ---------

void relu_inplace(Tensor *x) {
    int N = x->C * x->H * x->W;
    for (int i = 0; i < N; ++i) {
        if (x->data[i] < 0.0f) x->data[i] = 0.0f;
    }
}

void maxpool2x2_forward(const Tensor *x, Tensor *y) {
    const int C  = x->C;
    const int H  = x->H;
    const int W  = x->W;
    const int Ho = H / 2;
    const int Wo = W / 2;

    for (int c = 0; c < C; ++c) {
        const float *Xin = x->data + c * H * W;
        float *Yout      = y->data + c * Ho * Wo;

        for (int h = 0; h < Ho; ++h) {
            for (int w = 0; w < Wo; ++w) {
                int ih = h * 2;
                int iw = w * 2;

                float a  = Xin[ih * W + iw];
                float b  = Xin[ih * W + iw + 1];
                float c2 = Xin[(ih + 1) * W + iw];
                float d  = Xin[(ih + 1) * W + iw + 1];

                float m = a;
                if (b  > m) m = b;
                if (c2 > m) m = c2;
                if (d  > m) m = d;

                Yout[h * Wo + w] = m;
            }
        }
    }
}

void global_avg_pool_forward(const Tensor *x, float out[32]) {
    const int C = x->C;
    const int H = x->H;
    const int W = x->W;

    const float inv = 1.0f / (float)(H * W);
    for (int c = 0; c < C; ++c) {
        const float *Xin = x->data + c * H * W;
        float s = 0.0f;
        for (int i = 0; i < H * W; ++i) {
            s += Xin[i];
        }
        out[c] = s * inv;
    }
}

// --------- Fully-connected & sigmoid ---------

float fc_forward(const float *x32, const float *W32, float b) {
    float s = b;
    for (int i = 0; i < 32; ++i) {
        s += x32[i] * W32[i];
    }
    return s;
}

float sigmoidf(float z) {
    return 1.0f / (1.0f + expf(-z));
}

// --------- End-to-end forward ---------

float tiny_forward_prob(const TinyConvNet *net, const Tensor *in) {
    // static internal buffers to avoid malloc per frame
    // shapes: c1: 3/1 -> 8, c2: 8 -> 16, c3: 16 -> 32
    static float buf1[8 * 128 * 128];
    static float buf2[8 *  64 *  64];
    static float buf3[16 * 64 *  64];
    static float buf4[16 * 32 *  32];
    static float buf5[32 * 32 *  32];

    Tensor x = *in;  // C,H,W,data from caller

    // Conv1 + ReLU + MaxPool
    Tensor y1  = (Tensor){8, 128, 128, buf1};
    conv3x3_s1p1_forward(&x, &net->c1, &y1);
    relu_inplace(&y1);

    Tensor y1p = (Tensor){8, 64, 64, buf2};
    maxpool2x2_forward(&y1, &y1p);

    // Conv2 + ReLU + MaxPool
    Tensor y2  = (Tensor){16, 64, 64, buf3};
    conv3x3_s1p1_forward(&y1p, &net->c2, &y2);
    relu_inplace(&y2);

    Tensor y2p = (Tensor){16, 32, 32, buf4};
    maxpool2x2_forward(&y2, &y2p);

    // Conv3 + ReLU
    Tensor y3  = (Tensor){32, 32, 32, buf5};
    conv3x3_s1p1_forward(&y2p, &net->c3, &y3);
    relu_inplace(&y3);

    // Global average pool to length-32 vector
    float gap[32];
    global_avg_pool_forward(&y3, gap);

    // FC 32 -> 1, then sigmoid
    float logit = fc_forward(gap, net->fc_w, net->fc_b);
    return sigmoidf(logit);  // probability of "UNHEALTHY"
}
