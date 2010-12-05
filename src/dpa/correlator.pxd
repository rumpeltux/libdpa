from stdint cimport *

cdef extern from "correlator.h":
	ctypedef uint8_t hypo_in_t
	cdef cppclass Correlator:
		hypo_in_t * hypo
		double    * matrix
		uint8_t   * byte_matrix

		size_t samples
		size_t traces
		size_t keys
		size_t count

		Correlator(int,int,int)

		void update_matrix()
		void preprocess()

		void add_trace_u8(int hypo_idx, void * d) nogil
		void add_trace_u16(int hypo_idx, void * d) nogil
		void add_trace_float(int hypo_idx, void * d) nogil

	void correlator_add_trace_u8(Correlator * c, int hypo_idx, void * buf) nogil
	void correlator_add_trace_u16(Correlator * c, int hypo_idx, void * buf) nogil
	void correlator_add_trace_float(Correlator * c, int hypo_idx, void * buf) nogil

cdef struct _F:
	void (*add_trace)(Correlator * c, int hypo_idx, void * d) nogil
