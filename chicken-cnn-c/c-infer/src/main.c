#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <time.h>
#include <dirent.h>
#include <sys/stat.h>
#include <errno.h>

#include "tinycnn.h"
#include "loader.h"
#include "preprocess.h"

#ifndef THRESHOLD_DEFAULT
#define THRESHOLD_DEFAULT 0.50f
#endif

static int load_all_weights(TinyConvNet *net) {
    if (load_conv_from_bin("../weights/c1.bin", &net->c1, 1, 8, 3)) return -1;
    if (load_conv_from_bin("../weights/c2.bin", &net->c2, 8,16, 3)) return -1;
    if (load_conv_from_bin("../weights/c3.bin", &net->c3,16,32, 3)) return -1;
    if (load_fc_from_bin("../weights/fc.bin", net->fc_w, &net->fc_b)) return -1;
    return 0;
}

static float classify_file_prob(const TinyConvNet *net, const char *path) {
    float *img = load_grayscale_normalized_128(path);
    if (!img) {
        fprintf(stderr, "[ERROR] load failed: %s\n", path);
        return -1.0f; // signal error
    }
    Tensor in = (Tensor){1,128,128, img};
    float p = tiny_forward_prob(net, &in);
    free(img);
    return p;
}

static void usage(const char *prog) {
    fprintf(stderr,
        "Usage:\n"
        "  %s <image_path>\n"
        "  %s --dir <folder> [--threshold T]\n"
        "  (also supports previous --camera flow you may have)\n",
        prog, prog);
}

static int ends_with_ci(const char *s, const char *suf) {
    size_t n=strlen(s), m=strlen(suf);
    if (m>n) return 0;
    for (size_t i=0;i<m;i++){
        char a=s[n-m+i], b=suf[i];
        if (a>='A'&&a<='Z') a+=32;
        if (b>='A'&&b<='Z') b+=32;
        if (a!=b) return 0;
    }
    return 1;
}

typedef struct { char **items; int count, cap; } strvec;
static void sv_init(strvec *v){ v->items=NULL; v->count=0; v->cap=0; }
static void sv_push(strvec *v, const char *s){
    if (v->count==v->cap){
        v->cap = v->cap ? v->cap*2 : 32;
        v->items = (char**)realloc(v->items, v->cap*sizeof(char*));
    }
    v->items[v->count++] = strdup(s);
}
static int cmp_str(const void *a, const void *b){
    const char *sa=*(const char* const*)a, *sb=*(const char* const*)b;
    return strcmp(sa,sb);
}
static void sv_free(strvec *v){
    for(int i=0;i<v->count;i++) free(v->items[i]);
    free(v->items);
}

int main(int argc, char **argv) {
    // parse quick flags
    const char *dir_arg = NULL;
    float threshold = THRESHOLD_DEFAULT;

    if (argc>=2 && argv[1][0]=='-') {
        for (int i=1;i<argc;i++){
            if (!strcmp(argv[i],"--dir") && i+1<argc) dir_arg = argv[++i];
            else if (!strcmp(argv[i],"--threshold") && i+1<argc) threshold = (float)atof(argv[++i]);
            else if (!strcmp(argv[i],"--help") || !strcmp(argv[i],"-h")) { usage(argv[0]); return 0; }
        }
    }

    TinyConvNet net = (TinyConvNet){0};
    if (load_all_weights(&net)) { fprintf(stderr,"[ERROR] load weights\n"); return 1; }

    // ------- Single image mode -------
    if (!dir_arg && argc>=2 && argv[1][0] != '-') {
        const char *path = argv[1];
        float p = classify_file_prob(&net, path);
        if (p < 0.f) { free_conv(&net.c1); free_conv(&net.c2); free_conv(&net.c3); return 1; }
        const char *label = (p>=threshold) ? "UNHEALTHY" : "HEALTHY";
        printf("[RESULT] %s | prob_unhealthy=%.3f (threshold=%.2f) | file=%s\n",
               label, p, threshold, path);
        free_conv(&net.c1); free_conv(&net.c2); free_conv(&net.c3);
        return 0;
    }

    // ------- Directory batch mode -------
    if (dir_arg) {
        // list .jpg/.jpeg files
        DIR *d = opendir(dir_arg);
        if (!d){ perror(dir_arg); free_conv(&net.c1); free_conv(&net.c2); free_conv(&net.c3); return 1; }
        strvec files; sv_init(&files);

        struct dirent *ent;
        while ((ent = readdir(d)) != NULL){
            if (ent->d_name[0]=='.') continue;
            if (!(ends_with_ci(ent->d_name,".jpg") || ends_with_ci(ent->d_name,".jpeg"))) continue;
            // build "dir/name"
            char path[1024];
            snprintf(path, sizeof(path), "%s/%s", dir_arg, ent->d_name);
            // confirm it's a regular file
            struct stat st;
            if (stat(path,&st)==0 && S_ISREG(st.st_mode)) sv_push(&files, path);
        }
        closedir(d);

        if (files.count==0){
            fprintf(stderr, "[INFO] no JPEGs found in %s\n", dir_arg);
            sv_free(&files);
            free_conv(&net.c1); free_conv(&net.c2); free_conv(&net.c3);
            return 0;
        }

        qsort(files.items, files.count, sizeof(char*), cmp_str);
        printf("[INFO] Found %d image(s) in %s\n", files.count, dir_arg);

        // summary stats
        int n_healthy=0, n_unhealthy=0, n_err=0;
        double sum_p=0.0, min_p=1e9, max_p=-1e9;

        struct timespec t0, t1;
        clock_gettime(CLOCK_MONOTONIC, &t0);
        for (int i=0;i<files.count;i++){
            const char *path = files.items[i];
            struct timespec s0,s1; clock_gettime(CLOCK_MONOTONIC,&s0);

            float p = classify_file_prob(&net, path);

            clock_gettime(CLOCK_MONOTONIC,&s1);
            double ms = (s1.tv_sec - s0.tv_sec)*1000.0 + (s1.tv_nsec - s0.tv_nsec)/1e6;

            if (p < 0.f){
                n_err++;
                printf("[ERROR] failed | file=%s\n", path);
                continue;
            }
            const int unhealthy = (p >= threshold);
            if (unhealthy) n_unhealthy++; else n_healthy++;

            if (p<min_p) min_p=p;
            if (p>max_p) max_p=p;
            sum_p += p;

            printf("[RESULT] %-10s | p_unhealthy=%.3f | %.1f ms | %s\n",
                   unhealthy?"UNHEALTHY":"HEALTHY", p, ms, path);
        }
        clock_gettime(CLOCK_MONOTONIC, &t1);
        double total_ms = (t1.tv_sec - t0.tv_sec)*1000.0 + (t1.tv_nsec - t0.tv_nsec)/1e6;
        double fps = files.count > 0 ? (files.count*1000.0/total_ms) : 0.0;

        int n_ok = files.count - n_err;
        double avg_p = n_ok>0 ? (sum_p / n_ok) : 0.0;

        printf("\n--- SUMMARY ---\n");
        printf("files: %d  (ok=%d, errors=%d)\n", files.count, n_ok, n_err);
        printf("predicted: UNHEALTHY=%d, HEALTHY=%d (threshold=%.2f)\n", n_unhealthy, n_healthy, threshold);
        if (n_ok>0) printf("p_unhealthy: avg=%.3f  min=%.3f  max=%.3f\n", avg_p, min_p, max_p);
        printf("time: total=%.1f ms  avg=%.1f ms/frame  fps=%.2f\n",
               total_ms, (n_ok>0? total_ms/n_ok : 0.0), fps);

        sv_free(&files);
        free_conv(&net.c1); free_conv(&net.c2); free_conv(&net.c3);
        return 0;
    }

    usage(argv[0]);
    free_conv(&net.c1); free_conv(&net.c2); free_conv(&net.c3);
    return 1;
}
