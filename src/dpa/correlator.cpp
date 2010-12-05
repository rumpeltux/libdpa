/*
# Author: Hagen Fritsch, 2010
# Licensed under the terms of the GNU-GPL-3.0
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

#include "correlator.h"

#define NUM_THREADS 4

Correlator::Correlator(int _samples, int _traces, int _keys) {
	count   = 0;
	samples = _samples;
	traces  = _traces;
	keys    = _keys;
	
	sum        = new intermediate_result_t[samples];
	square_sum = new intermediate_result_t[samples];
	mult_sum   = new intermediate_result_t[keys * samples];

	memset(sum,        0, sizeof(intermediate_result_t) * samples);
	memset(square_sum, 0, sizeof(intermediate_result_t) * samples);
	memset(mult_sum,   0, sizeof(intermediate_result_t) * samples * keys);

	key_avg    = new double[keys];
	key_stddev = new double[keys];

	hypo       = new hypo_in_t[keys * traces];

	matrix     = new double[keys * samples];
	byte_matrix= new uint8_t[keys * samples];

	key_lock   = new pthread_mutex_t[keys];
	for(size_t i=0;i<keys;i++)
		pthread_mutex_init(&key_lock[i], NULL);
	pthread_mutex_init(&data_lock, NULL);
}

Correlator::~Correlator() {
	delete [] sum;
	delete [] square_sum;
	delete [] mult_sum;
	delete [] key_avg;
	delete [] key_stddev;
	delete [] matrix;
	delete [] byte_matrix;
	delete [] key_lock;
}

#define add_trace(name, data_in_t) \
void Correlator::add_trace_##name(int hypo_idx, data_in_t * d) {\
	size_t i,j;\
	hypo_in_t key;\
	for(j=0;j<keys;j++) {\
		key = hypo[j*traces + hypo_idx];\
		pthread_mutex_lock(&key_lock[j]);\
		for(i=0;i<samples;i++)\
			mult_sum[j*samples + i] += key * d[i];\
		pthread_mutex_unlock(&key_lock[j]);\
	}\
	pthread_mutex_lock(&data_lock);\
	for(i=0;i<samples;i++) {\
		sum[i]        += d[i];\
		square_sum[i] += d[i] * d[i];\
	}\
	count++;\
	pthread_mutex_unlock(&data_lock);\
} \
extern "C" { \
void correlator_add_trace_##name(Correlator * c, int hypo_idx, data_in_t * buf) {\
	c->add_trace_##name(hypo_idx, buf);\
} \
}

add_trace(u8,   uint8_t)
add_trace(u16,  uint16_t)
add_trace(float,float)

/* updates the output matrix by calculating the correlation values
 * from the intermediate result */
void Correlator::update_matrix() {
	size_t i,j;
	double min=-1, max=1;
	if(count < traces) fprintf(stderr, "Warning: this is a prelimary result (%zu / %zu)\n", count, traces);
	if(count > traces) fprintf(stderr, "Error: too many traces read (%zu / %zu)\n", count, traces);

	for(j=0;j<keys;j++) {
		for(i=0;i<samples;i++) {
			double cur_avg = (double) sum[i] / count;

			double cur = (mult_sum[j*samples + i] - sum[i] * key_avg[j]) 
			                   / sqrt((double) square_sum[i] / count - cur_avg * cur_avg)
			                   / key_stddev[j]
			                   / count; //(count - 1);
			matrix[j*samples + i] = cur;
			if(cur > max) max = cur;
			if(cur < min) min = cur;

			/*if(i <= 1) fprintf(stderr, "[%d,%d] %lf %lf %lf %zd %lf %lf %lf %lf\n", i, j,
			mult_sum[j*samples + i] - sum[i] * key_avg[j],
			sqrt((double) square_sum[i] / count - cur_avg * cur_avg),
			matrix[j*samples + i],
			count,
			mult_sum[j*samples + i],
			(double) sum[i] * key_avg[j],
			key_stddev[j],
			key_avg[j]);/**/
		}
	}
	for(j=0; j<keys*samples; j++)
		byte_matrix[j] = ((double) matrix[j] - min) * 255. / (max-min);
}

/* calculates average and standard deviation for the hypothesis vectors */
void Correlator::preprocess() {
	size_t i,j;
	int64_t sum, sq_sum;
	hypo_in_t cur;
	for(j=0;j<keys;j++) {
		sum = sq_sum = 0;
		for(i=0;i<traces;i++) {
			cur = hypo[j*traces + i];
			sum += cur;
			sq_sum += cur * cur;
		}
		key_avg[j]    = (double) sum / traces;
		key_stddev[j] = sqrt((double) sq_sum / traces - key_avg[j] * key_avg[j]);
		/*if(j == 0) fprintf(stderr, "std_dev: %lf %lld %lld %zd\n", key_stddev[j], sq_sum, sum, traces);*/
	}
}

/* C API functions
 * these are accessable even if CPP code cannot be directly used */
extern "C" {

/* dumps the matrix in an octave readable format to f */
void dump_matrix(FILE * f, Correlator * c) {
	size_t i,j;
	c->update_matrix();
	for(i=0;i<c->keys;i++) {
		for(j=0;j<c->samples;j++)
			fprintf(f, "%lf ", c->matrix[i*c->samples + j]);
		fprintf(f, "\n");
	}
}

/*
 * some accessability functions for external libraries *
 */

#ifdef SHARED
/* creates a new correlator instance */
Correlator * correlator_init(int samples, int traces, int keys) {
	return new Correlator(samples, traces, keys);
}

void correlator_free(Correlator * c) {
	delete c;
}

void correlator_preprocess(Correlator * c) {
	c->preprocess();
}

hypo_in_t * correlator_get_hypo(Correlator * c) {
	return c->hypo;
}

uint8_t * correlator_get_byte_matrix(Correlator * c) {
	return c->byte_matrix;
}

double * correlator_get_matrix(Correlator * c) {
	c->update_matrix();
	return c->matrix;
}
#endif
}
