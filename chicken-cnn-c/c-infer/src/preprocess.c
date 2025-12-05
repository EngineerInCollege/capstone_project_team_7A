#define STB_IMAGE_IMPLEMENTATION
#include "../third_party/stb_image.h"
#define STB_IMAGE_RESIZE2_IMPLEMENTATION
#include "../third_party/stb_image_resize2.h"

#include "preprocess.h"
#include <stdlib.h>
#include <string.h>

// grayscale helper
static inline uint8_t rgb_to_gray_u8(uint8_t r, uint8_t g, uint8_t b){
    float y = 0.299f*r + 0.587f*g + 0.114f*b;
    if(y<0) y=0; if(y>255) y=255;
    return (uint8_t)(y + 0.5f);
}

// Crop a center square
static void center_crop_gray_square(const uint8_t *src, int w, int h, uint8_t *dst, int side) {
    // size = min(w,h)
    int cx = w/2, cy = h/2;
    int half = side/2;
    int x0 = cx - half, y0 = cy - half;
    for (int y=0; y<side; ++y) {
        const uint8_t* row = src + (y0 + y)*w;
        memcpy(dst + y*side, row + x0, side);
    }
}

static void resize_gray_128(const uint8_t *gray_in, int inW, int inH, float *out128){
    // use stb resize to 128x128 u8 then normalize to [-1,1]
    int side = (inW < inH ? inW : inH);
    uint8_t *sq = (uint8_t*)malloc(side*side);
    center_crop_gray_square(gray_in, inW, inH, sq, side);
    
    uint8_t *tmp = (uint8_t*)malloc(128*128);
    stbir_resize_uint8_linear(sq, side, side, 0, tmp, 128, 128, 0, 1);
    
    for(int i=0;i<128*128;++i){
        float v = (tmp[i]/255.0f - 0.5f) / 0.5f; // [-1,1]
        out128[i] = v;
    }
    free(tmp); free(sq);
}

float *load_grayscale_normalized_128(const char *image_path){
    int w,h,comp;
    unsigned char *img = stbi_load(image_path, &w, &h, &comp, 3); // force RGB
    if(!img) return NULL;
    // convert to gray
    uint8_t *gray = (uint8_t*)malloc(w*h);
    for(int i=0;i<w*h;++i){
        uint8_t r=img[3*i], g=img[3*i+1], b=img[3*i+2];
        gray[i]=rgb_to_gray_u8(r,g,b);
    }
    float *out = (float*)malloc(128*128*sizeof(float));
    resize_gray_128(gray, w, h, out);
    free(gray);
    stbi_image_free(img);
    return out;
}

void preprocess_from_rgb888(const uint8_t *rgb, int w, int h, int stride, float out128[128*128]){
    // pack to gray buffer first
    uint8_t *gray=(uint8_t*)malloc(w*h);
    const uint8_t *row=rgb;
    for(int y=0;y<h;++y){
        const uint8_t *p=row;
        for(int x=0;x<w;++x){
            uint8_t r=p[0], g=p[1], b=p[2];
            gray[y*w+x]=rgb_to_gray_u8(r,g,b);
            p+=3;
        }
        row += stride; // bytes per row (may equal w*3)
    }
    resize_gray_128(gray, w, h, out128);
    free(gray);
}

void preprocess_from_bgr888(const uint8_t *bgr, int w, int h, int stride, float out128[128*128]){
    uint8_t *gray=(uint8_t*)malloc(w*h);
    const uint8_t *row=bgr;
    for(int y=0;y<h;++y){
        const uint8_t *p=row;
        for(int x=0;x<w;++x){
            uint8_t b=p[0], g=p[1], r=p[2];
            gray[y*w+x]=rgb_to_gray_u8(r,g,b);
            p+=3;
        }
        row += stride;
    }
    resize_gray_128(gray, w, h, out128);
    free(gray);
}
