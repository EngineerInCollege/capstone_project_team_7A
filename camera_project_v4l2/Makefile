TARGET1=camera_project_v4l2
TARGET2=video_interface_test

SOURCES1=camera_project_v4l2.c
SOURCES2=video_interface_test.c \
         video_interface.c

OBJECTS1=$(patsubst %.cpp,%.o,$(patsubst %.c,%.o,$(SOURCES1)))
OBJECTS2=$(patsubst %.cpp,%.o,$(patsubst %.c,%.o,$(SOURCES2)))

CFLAGS=-Wall \
       -Werror \
       -g

all: $(TARGET1) $(TARGET2)

clean:
	rm -f $(OBJECTS1) $(TARGET1) $(OBJECTS2) $(TARGET2)

$(TARGET1): $(OBJECTS1)
	gcc $^ $(CFLAGS) -o $@ -lm -lpthread

$(TARGET2): $(OBJECTS2)
	gcc $^ $(CFLAGS) -o $@ -lm -lpthread -lswscale

%.o:%.c
	gcc $(CFLAGS) -c $< -o $@
