CC=gcc
CFLAGS=-O3 -mcpu=cortex-a72 -ffast-math -Iinclude -Ithird_party
LDFLAGS=-lm

SRC=src/tinycnn.c src/preprocess.c src/loader.c src/main.c
BIN=pi_infer

all: $(BIN)

$(BIN): $(SRC)
	$(CC) $(CFLAGS) -o $@ $(SRC) $(LDFLAGS)

clean:
	rm -f $(BIN)
