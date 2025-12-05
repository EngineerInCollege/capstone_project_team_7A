#include "loader.h"
#include <stdio.h>
#include <stdlib.h>

int load_conv_from_bin(const char *path, Conv2D *L, int inC, int outC, int k){
    init_conv(L, inC, outC, k);
    FILE *f=fopen(path,"rb");
    if(!f){ perror(path); return -1; }
    size_t wcount=(size_t)outC*inC*k*k;
    if(fread(L->w, sizeof(float), wcount, f)!=wcount){ perror("read W"); fclose(f); return -1; }
    if(fread(L->b, sizeof(float), outC, f)!=(size_t)outC){ perror("read b"); fclose(f); return -1; }
    fclose(f);
    return 0;
}

int load_fc_from_bin(const char *path, float w32[32], float *b){
    FILE *f=fopen(path,"rb");
    if(!f){ perror(path); return -1; }
    if(fread(w32, sizeof(float), 32, f)!=32){ perror("read fc W"); fclose(f); return -1; }
    if(fread(b, sizeof(float), 1, f)!=1){ perror("read fc b"); fclose(f); return -1; }
    fclose(f);
    return 0;
}
