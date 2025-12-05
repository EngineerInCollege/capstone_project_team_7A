#include "tinycnn.h"
#include <stdlib.h>
#include <math.h>
#include <string.h>

void init_conv(Conv2D *L, int inC, int outC, int k) {
    L->inC=inC; L->outC=outC; L->k=k;
    size_t wcount = (size_t)outC*inC*k*k;
    L->w = (float*)aligned_alloc(64, wcount*sizeof(float));
    L->b = (float*)aligned_alloc(64, outC*sizeof(float));
}

void free_conv(Conv2D *L){
    if(L->w) free(L->w);
    if(L->b) free(L->b);
    L->w=L->b=NULL;
}

void conv3x3_s1p1_forward(const Tensor *x, const Conv2D *L, Tensor *y) {
    const int C=x->C,H=x->H,W=x->W, OC=L->outC, IC=L->inC;
    const int K=3, P=1;
    for(int oc=0; oc<OC; ++oc){
        for(int h=0; h<H; ++h){
            for(int w=0; w<W; ++w){
                float sum=L->b[oc];
                for(int ic=0; ic<IC; ++ic){
                    const float *Xin = x->data + ic*H*W;
                    const float *Kern= L->w + (((oc*IC)+ic)*K*K);
                    for(int kh=0; kh<K; ++kh){
                        int ih=h+kh-P; if((unsigned)ih>=(unsigned)H) continue;
                        for(int kw=0; kw<K; ++kw){
                            int iw=w+kw-P; if((unsigned)iw>=(unsigned)W) continue;
                            sum += Xin[ih*W + iw] * Kern[kh*K + kw];
                        }
                    }
                }
                y->data[oc*H*W + h*W + w] = sum;
            }
        }
    }
}

void relu_inplace(Tensor *x){
    int N=x->C*x->H*x->W;
    for(int i=0;i<N;++i) if(x->data[i]<0) x->data[i]=0;
}

void maxpool2x2_forward(const Tensor *x, Tensor *y){
    const int C=x->C,H=x->H,W=x->W, Ho=H/2, Wo=W/2;
    for(int c=0;c<C;++c){
        const float *Xin=x->data + c*H*W;
        float *Yout = y->data + c*Ho*Wo;
        for(int h=0; h<Ho; ++h){
            for(int w=0; w<Wo; ++w){
                int ih=h*2, iw=w*2;
                float a=Xin[ih*W+iw], b=Xin[ih*W+iw+1];
                float c2=Xin[(ih+1)*W+iw], d=Xin[(ih+1)*W+iw+1];
                float m=a; if(b>m)m=b; if(c2>m)m=c2; if(d>m)m=d;
                Yout[h*Wo+w]=m;
            }
        }
    }
}

void global_avg_pool_forward(const Tensor *x, float out[32]){
    const int C=x->C,H=x->H,W=x->W;
    const float inv = 1.0f/(H*W);
    for(int c=0;c<C;++c){
        const float *Xin=x->data + c*H*W;
        float s=0.f;
        for(int i=0;i<H*W;++i) s+=Xin[i];
        out[c]=s*inv;
    }
}

float fc_forward(const float *x32, const float *W32, float b){
    float s=b;
    for(int i=0;i<32;++i) s += x32[i]*W32[i];
    return s;
}

float sigmoidf(float z){ return 1.f/(1.f+expf(-z)); }

float tiny_forward_prob(const TinyConvNet *net, const Tensor *in){
    // internal buffers (static to avoid malloc each frame)
    static float buf1[8*128*128], buf2[8*64*64], buf3[16*64*64], buf4[16*32*32], buf5[32*32*32];
    Tensor x = *in;

    Tensor y1  = (Tensor){8,128,128, buf1};
    conv3x3_s1p1_forward(&x, &net->c1, &y1); relu_inplace(&y1);
    Tensor y1p = (Tensor){8,64,64, buf2};
    maxpool2x2_forward(&y1, &y1p);

    Tensor y2  = (Tensor){16,64,64, buf3};
    conv3x3_s1p1_forward(&y1p, &net->c2, &y2); relu_inplace(&y2);
    Tensor y2p = (Tensor){16,32,32, buf4};
    maxpool2x2_forward(&y2, &y2p);

    Tensor y3  = (Tensor){32,32,32, buf5};
    conv3x3_s1p1_forward(&y2p, &net->c3, &y3); relu_inplace(&y3);

    float gap[32];
    global_avg_pool_forward(&y3, gap);
    float logit = fc_forward(gap, net->fc_w, net->fc_b);
    return sigmoidf(logit);
}
