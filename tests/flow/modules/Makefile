# find the OS
uname_S := $(shell sh -c 'uname -s 2>/dev/null || echo not')

# Compile flags for linux / osx
ifeq ($(uname_S),Linux)
	SHOBJ_CFLAGS ?=  -fno-common -g -ggdb
	SHOBJ_LDFLAGS ?= -shared -Bsymbolic
else
	SHOBJ_CFLAGS ?= -dynamic -fno-common -g -ggdb
	SHOBJ_LDFLAGS ?= -bundle -undefined dynamic_lookup
endif
CFLAGS = -I$(RM_INCLUDE_DIR) -Wall -g -fPIC -lm -std=gnu99  
CC=gcc

all: module1.so module2.so

module1.so: module1.o
	$(LD) -o $@ module1.o $(SHOBJ_LDFLAGS) $(LIBS)

module2.so: module2.o
	$(LD) -o $@ module2.o $(SHOBJ_LDFLAGS) $(LIBS)

clean:
	rm -rf *.xo *.so *.o

FORCE:
