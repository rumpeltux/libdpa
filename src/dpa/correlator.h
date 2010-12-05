#include <stdint.h>

typedef uint8_t hypo_in_t;
typedef double  intermediate_result_t;
#define DATA_IN_FMTSTRING "%hhu"

class Correlator {
	intermediate_result_t * sum;
	intermediate_result_t * mult_sum;
	intermediate_result_t * square_sum;

	double    * key_avg;
	double    * key_stddev;

	pthread_mutex_t * key_lock;
	pthread_mutex_t data_lock;
    public:
	hypo_in_t * hypo;
	double    * matrix;
	uint8_t   * byte_matrix;

	size_t samples;
	size_t traces;
	size_t keys;
	size_t count;

	Correlator(int,int,int);
	~Correlator();
	void add_trace_u8(int, uint8_t *);
	void add_trace_u16(int, uint16_t *);
	void add_trace_float(int, float *);

	void update_matrix();
	void preprocess();
};

extern "C" {
	void dump_matrix(FILE * f, Correlator * c);

	void correlator_add_trace_u8(Correlator * c, int hypo_idx, uint8_t * buf);
	void correlator_add_trace_u16(Correlator * c, int hypo_idx, uint16_t * buf);
	void correlator_add_trace_float(Correlator * c, int hypo_idx, float * buf);

	Correlator * correlator_init(int samples, int traces, int keys);
	void         correlator_free(Correlator * c);

	void correlator_preprocess(Correlator * c);
	hypo_in_t * correlator_get_hypo(Correlator * c);
	uint8_t   * correlator_get_byte_matrix(Correlator * c);
	double    * correlator_get_matrix(Correlator * c);
}
