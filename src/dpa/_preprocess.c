/*
# Author: Hagen Fritsch, 2010
# Licensed under the terms of the GNU-GPL-3.0
*/
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <math.h>


#define ABS(x)		(((x)>0)?(x):(-(x)))
#define SSCALE(x, issigned, scale) ((issigned) + ((x) - (issigned)) * (scale))

#ifdef __cplusplus
extern "C" {
#else

/* have use uint8_t as a save default for non c++ environments */
#  ifndef data_in_t
	typedef uint8_t data_in_t;
#  endif
#  ifndef data_out_t
	typedef uint8_t data_out_t;
#  endif
#endif

#ifndef NAME
#  define NAME(x) x
#endif

/* define the rasterization configuration only once (__PREPROCESS_H is set at
 * the end of this file which may be included more than once) */
// TODO: raster_config should be obsoleted and integrated in the appropriate
// TODO  rasterization functions
#ifndef __PREPROCESS_H
struct _raster_config {
	int trigger;
	int pause_trigger;
	int min_pause;
	int max_pause;
	int header_size;
} raster_config = {120, 1100, 3, 6, 128};
#endif

#ifdef __cplusplus
}
template <class data_out_t, class data_in_t> class Preprocess {
	public:
#endif

/***********************************
 * rasterization support functions */
float NAME(compare)(const data_in_t *d1, const data_in_t *d2, int len) {
	int cnt;
	float res = 0;
	
	for(cnt=0; cnt < len; cnt++) {
		float val = *d1 - *d2;
		res += (val*val);
		d1++;
		d2++;
	}
	
	return res;
}

void NAME(spline)(data_out_t *out, const data_in_t * in, int outsize, int insize) {
	int i;
	double scale = (double) (insize-1) / (outsize-1);
	for(i=0;i<outsize;i++) {
		double inpos = i * scale;
		int a = inpos;
		// TODO should we do arithmetic rounding here?
		out[i] = in[a] * (1 - inpos + a) + in[a+1] * (inpos - a); //linear for now
	}
}

size_t NAME(raster_write)(data_out_t * out, const data_in_t *d, int dlen, int padlen) {
	NAME(spline)(out, d, dlen+padlen, dlen);
	return dlen+padlen;
}

int NAME(raster)(data_out_t * out, const data_in_t * in, size_t len, size_t * out_size, int raster, const data_in_t * edge, size_t edge_len) {
	int cnt;
	int last_pos = 0;

	int max_distance = 0;
	int start = 0;
	float *comp_vals;

	const data_in_t *tdata;
	
	const data_in_t * in_ptr = in;
	//size_t in_len = len;
	data_out_t * out_ptr = out;	
	
	in_ptr += raster_config.header_size;
	// avoid flipping into negative
	if(len < raster_config.header_size + edge_len) return -1;
	len -= raster_config.header_size;
	
	tdata = in_ptr;
	
	comp_vals = (float *) malloc(len * sizeof(float));
	//if(!comp_vals) { perror("malloc"); exit(0); }
	
	// calc edge matches
	for(cnt=0; cnt < (len - edge_len); cnt++) {
		float diff = NAME(compare)(tdata+cnt, edge, edge_len);
		
		comp_vals[cnt] = diff;		
	}
	
	for(cnt=0; cnt < (len - edge_len); ) {
		
		if(comp_vals[cnt] < raster_config.trigger) {
			int min_val = comp_vals[cnt];
			int min_pos = cnt;
			int cnt2;
			
			for(cnt2 = cnt+1; cnt2 < cnt + raster / 2 + 1; cnt2++) {
				if(comp_vals[cnt2] < min_val) {
					min_val = comp_vals[cnt2];
					min_pos = cnt2;
				}
			}
			
			//printf("%d\n",min_pos);
			
			if(last_pos > 0) {
				int distance = min_pos - last_pos;
				
				
				if(raster && start >= raster_config.min_pause && distance < raster_config.pause_trigger / 2) {
					if(distance >= raster) {
						fprintf(stderr, "distance: %d @%d\n", distance, last_pos);
					}
					if(min_pos < len - 2*raster) {
						if(distance < 0.9 * (raster-5)) fprintf(stderr, "distance: %d @%d\n", distance, last_pos);
						assert(distance < 1.1 * raster);
						assert(distance > 0.9 * (raster-5));
					}

					out_ptr += NAME(raster_write)(out_ptr, in_ptr+last_pos, distance, raster - distance);
				}
				else if(!raster)
					printf("%d\n",distance);
				
				if(min_pos < len - 2*max_distance)
				if(distance > max_distance && distance < raster_config.pause_trigger)
					max_distance = distance;

				if(distance > raster_config.pause_trigger) {
					assert(start < raster_config.max_pause);
					start++;
					if(start >= raster_config.min_pause && !raster)
						printf("last_pos: %d, min_pos: %d\n", last_pos, min_pos);
				}
			}
			
			last_pos = min_pos;
			
			cnt = cnt2 + 1;
		}
		else
			cnt++;
	}
	free(comp_vals);
	fprintf(stderr,"max_distance: %d\n",max_distance);
	if(start != raster_config.min_pause) { fprintf(stderr,"did not start %d", start); return 1; }
	*out_size = out_ptr - out;
	return start;
}

/*********************************
 * basic preprocessing functions */

/* an n-step average filter, reducing output size by factor skip. scales output according to scale */
void NAME(average_filter)(data_out_t * out, const data_in_t * in, size_t len, size_t n, size_t skip, double scale, int issigned) {
	double avg = 0;
	size_t i, offset;
	for(i = 0; i < n-1; i++)
		avg += in[i];
	for(i = n-1, offset=0; i < len; i++, offset++) {
		avg += in[i];
		if(offset % skip == 0)
			out[offset/skip] = SSCALE((double) avg / n, issigned, scale);
		avg -= in[offset];
	}
}

void NAME(square_buf)(data_out_t * out, const data_in_t * in, size_t len) {
	size_t i;
	for(i=0; i<len; i++)
		out[i] = in[i] * in[i];
}
/* processes a trace updating the sum and square_sum buffers */
void NAME(add_average)(data_out_t * out_sum, data_out_t * out_square_sum, const data_in_t * in, size_t len) {
	size_t i;
	for(i=0; i<len; i++) {
		out_sum[i] += in[i];
		if(out_square_sum) out_square_sum[i] += in[i] * in[i];
	}
}
void NAME(absolute)(data_in_t * out, const data_in_t * in, size_t len, int middle) {
	size_t i;
	for(i=0; i<len;i++)
		out[i] = in[i] < middle ? middle + (middle - in[i]) : in[i];
}

/************************************
 * peak extraction
 ************************************
 * extract the high peaks only
 * we keep an updating average and standard deviation
 * and return the maximum value after reaching in[i] < avg - std_dev and in[i_earlier] > avg + std_dev
 * by which we feel confident to skip pauses in the data channel */
// TODO make that data_out_t, allow for additional peak integration
size_t NAME(peak_extract)(data_in_t * out, const data_in_t * in, size_t len, double avg, double std_dev, size_t break_length, size_t break_count) {
	double max = in[0];
	int state = 0;
	double trsh_low = avg - std_dev;
	double trsh_high= avg + std_dev;
	size_t pos=0;
	size_t last_pos=0;
	size_t i;
	for(i=0;i<len;i++) {
		if(state == 0 && in[i] < trsh_low) { state++; max = in[i]; } /* initialize once */
		if(state != 0 && in[i] > max) max = in[i];
		if(state == 1 && in[i] > trsh_high) state++;
		if(state == 2 && in[i] < trsh_low) {
			state = 1;
			out[pos++] = max;
			max = in[i];
			if(break_count && i - last_pos > break_length) {
				if(--break_count == 0)
					pos = 0; //reset output, (skipping first peak after pause!)
			}
			last_pos = i;
		}
	}
	return pos;
}

void NAME(scale)(size_t len, data_out_t * out, const data_in_t * in, int issigned, double scale) {
	int i;
	//issigned = issigned ? 128 : 0
	for(i=0;i<len;i++)
		out[i] = issigned + (in[i] - issigned) * scale;
}

void NAME(diff)(size_t len, data_out_t * out, const data_in_t * a, const data_in_t * b, int absolute) {
	int i;
	int issigned = ((data_out_t) -1) < 0 ? 0 : ((data_out_t) -1) / 2 + 1;
	for(i=0;i<len;i++) {
		out[i] = a[i] - b[i];
		if(absolute && a[i] < b[i])
			out[i] = b[i] - a[i];
		if(!absolute) out[i] += issigned;
	}
}

void NAME(integrate)(data_out_t * out, const data_in_t * in, size_t len, int samples) {
	int i;
	data_out_t tmp = 0;
	for(i=0;i<samples-1;i++)
		tmp += in[i];
	for(i=samples-1;i<len;i++) {
		tmp += in[i];
		out[i-samples+1] = tmp;
		tmp -= in[i-samples+1];
	}
}

void NAME(analyze)(const data_in_t * in, size_t len, double * average, double * variance, double * min, double * max) {
	double _avg = in[0];
	double var = 0;
	double avg;
	size_t i;
	data_in_t _min = in[0];
	data_in_t _max = in[0];
	
	for(i=1; i<len; i++) {
		_avg += in[i];
		if(in[i] < _min) _min = in[i];
		if(in[i] > _max) _max = in[i];
	}
	
	avg = (double) _avg / len;

	if(variance) {
		for(i=0; i<len; i++) {
			double dev = in[i] - avg;
			var += (dev * dev) / len;
		}
	}

	if(average)  *average  = avg;
	if(variance) *variance = var;
	if(min)      *min      = _min;
	if(max)      *max      = _max;
}

//TODO rewrite to allow external definitions.
//     raise exceptions or st similar
int NAME(normalize)(data_out_t * out, const data_in_t * in, size_t len, double min, double max) {
	int issigned = ((data_out_t) -1) < 0;	//probably superfluous
	data_out_t type_max = issigned ? -1 ^ (1 << (sizeof(data_out_t) * 8 - 1)) : -1;
	data_out_t type_min = type_max + 1;
	double scale = (type_max - type_min) / (max - min);

	size_t i;
	for(i=0;i<len;i++) {
		if(in[i] > max || in[i] < min) return -i;
		out[i] = (in[i] - min) * scale + type_min;
	}
	return 1;
}

int NAME(normalize_avg)(size_t len, data_out_t * out, const data_in_t * in, size_t period) {
	double min, max;
	double average;
	//size_t norm_len = len - len % period;
	size_t i;

	NAME(analyze)(in, len, &average, NULL, &min, &max);

	int issigned = ((data_out_t) -1) < 0;	//probably superfluous
	data_out_t target_avg = issigned ? 0 : ((data_out_t) -1) / 2 + 1;
	data_out_t type_max = issigned ? -1 ^ (1 << (sizeof(char) * 8 - 1)) : -1;
	data_out_t type_min = type_max + 1;
	//double scale = // no scaling for now. makes only sense in a global manner
	if(max - average > type_max - target_avg || average - min > target_avg - type_min) {
		fprintf(stderr, "overflow (avg: %f, max: %d, min: %d)\n", average, (int) max, (int) min);
		return -1;
	}

	for(i=0;i<len;i++)
		out[i] = in[i] - average + target_avg;

	return 0;
}

void NAME(rectify)(data_out_t * out, const data_in_t * in, size_t len, double avg) {
	size_t i;
	for(i=0;i<len;i++)
		out[i] = in[i] > avg ? in[i] - avg : avg - in[i];
}

void NAME(reorder)(data_out_t * out, const data_in_t * in, size_t len, size_t period) {
	size_t i;
	size_t poff[period];
	poff[0] = 0;
	for(i=1;i<period;i++)
		poff[i] = poff[i-1] + (len + period - i) / period;
	for(i=0;i<len;i++)
		out[ poff[i % period] + i / period ] = in[i];
}

size_t NAME(apply_filter)(data_out_t * out, const data_in_t * in, size_t len, const int8_t * filter, size_t filter_len, double scale, int issigned) {
	unsigned int filter_sum = 0;
	double tmp;
	int i,j;
	for(i=0;i<filter_len;i++) filter_sum+=filter[i];
	
	for(i=0;i<len-filter_len+1;i++) {
		tmp = 0;
		for(j=0; j<filter_len; j++)
			tmp += filter[j] * in[i+j];
		out[i] = (data_out_t) (issigned + ( ((double) tmp / (double) filter_sum) - issigned) * scale);
	}
	return len-filter_len;
}

/* ********************************************
 * frequency filtering using fourier transform
 * - uses libfftw3 for the transformation
 * TODO currently only implements bandpass operations
 * TODO should be more flexible */

#ifdef WITH_FFT
#include <complex.h>
#include <fftw3.h>

#ifndef __PREPROCESS_H
fftw_plan fftw_plan_forward = NULL;
fftw_plan fftw_plan_backward = NULL;
int fftw_plan_size=0;
#endif

void NAME(fft_filter)(data_out_t * out_data, const data_in_t * in_data, size_t len, int start, int stop, double *scale, double *offset) {
	double *in;
	fftw_complex *out;
	int i;


	/* allocate memory */
	in = (double*) fftw_malloc(sizeof(double) * len + 2);
	out = (fftw_complex*) fftw_malloc(sizeof(fftw_complex) * (len / 2 + 1));

	/* compute a new computation plan unless there is already one matching the input size */
	if(len != fftw_plan_size) {
		if(fftw_plan_forward) fftw_destroy_plan(fftw_plan_forward);
		if(fftw_plan_backward) fftw_destroy_plan(fftw_plan_backward);
		fftw_plan_forward  = fftw_plan_dft_r2c_1d(len, in, out, FFTW_ESTIMATE);
		fftw_plan_backward = fftw_plan_dft_c2r_1d(len, out, in, FFTW_ESTIMATE);
	}

	/* fill input data */
	for(i=0;i<len;i++)
		in[i] = in_data[i];

	fftw_execute(fftw_plan_forward); // do the fft

	/* band pass */
	//fprintf(stderr, "band pass: %d to %d\n", start, stop);
	for(i=0;i<start;i++)
		out[i] = 0;
	for(i=stop;i<len/2+1;i++)
		out[i] = 0;

	fftw_execute(fftw_plan_backward); // reverse fft

	int autoscale = *scale == 0;
	if(autoscale) {
		double min, max;
		min = max = in[0];
		for(i=1;i<len;i++) {
			if(in[i] < min) min = in[i];
			if(in[i] > max) max = in[i];
		}
		*offset = min;
		*scale  = 255 / (max - min);
		//fprintf(stderr, "autoscale: %f (%f)\n", *scale, *offset);
	} else
		*scale /= len;

	for(i=0;i<len;i++)
		out_data[i] = (in[i] - *offset) * *scale;

	fftw_free(in); fftw_free(out);
}
#endif

int NAME(load_buf)(const char * filename, data_in_t * buf, size_t len) {
	FILE * f = fopen(filename, "r");
	if(!f) {
		fprintf(stderr, "%s", filename);
		perror("fopen");
		return 0;
	}
	if(fread(buf, sizeof(data_in_t), len, f) < len)  {
		fprintf(stderr, "%s", filename);
		perror("fread");
		fclose(f);
		return 0;
	}
	fclose(f);
	return 1;
}

int NAME(write_buf)(const char * filename, const data_in_t * buf, size_t len) {
	FILE * f = fopen(filename, "w");
	if(!f) {
		fprintf(stderr, "%s", filename);
		perror("fopen");
		return 0;
	}
	if(fwrite(buf, sizeof(data_in_t), len, f) != len) {
		fprintf(stderr, "%s", filename);
		perror("fwrite");
		fclose(f);
		return 0;
	}
	fclose(f);
	return 1;
}

/* some helper functions for typeindifferent buffer access from python */
void NAME(buffer_set_value)(data_out_t * buf, size_t i, double v) {
	buf[i] = v;
}

double NAME(buffer_get_value)(data_in_t * buf, size_t i) {
	return buf[i];
}

#ifdef __cplusplus
}; // finish the class declaration
#endif

#define __PREPROCESS_H
