PRGS=preprocess.so correlator.so 
#preprocessor.so correlation.so
CFLAGS=-fPIC -lm -lfftw3 -DWITH_FFT
AUTOGEN=preprocess.c preprocess.h preprocess.pxd types.pxh

default: $(PRGS) $(AUTOGEN)

$(AUTOGEN): autogen _preprocess.c
	grep NAME _preprocess.c | ./autogen $@ > $@

%.so: %.c
	gcc $(CFLAGS) -shared $< -o $@

%.so: %.cpp
	g++ -g -fPIC -shared -DSHARED -o $@ $<

clean:
	rm $(PRGS) $(AUTOGEN) preprocessor.c *.o correlation.cpp preprocessor.cpp || true
