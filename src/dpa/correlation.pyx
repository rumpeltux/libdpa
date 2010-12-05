# Author: Hagen Fritsch, 2010
# Licensed under the terms of the GNU-GPL-3.0

import os, sys
import pickle
from preprocessor cimport Buffer, _Buffer
from preprocessor import types, Buffer#, _Buffer
from correlator cimport Correlator as CCorrelator, correlator_add_trace_u8, correlator_add_trace_u16, correlator_add_trace_float, _F
from stdint cimport *

cdef class Correlator:
	"""
	Correlator(samples, traces, keys)
	
	creates a new :class:`Correlator` instance used to rapidly calculate
	correlations in a DPA scenario

	*samples*
		is the number of samples in each trace, i.e. the trace length
	*traces*
		is the total number of traces to be processed
	*keys*
		is the number of hypothesis

	>>> c = Correlator(2, 3, 1) #create a new correlator
	>>> c.hypo[0] = 5           #calculate a hypothesis for each trace
	>>> c.hypo[1] = 4
	>>> c.hypo[2] = 3
	>>> c.preprocess()          #preprocess the hypothesis
	>>> from preprocessor import buffer_from_list
	>>> c.add_trace(buffer_from_list(types.uint8_t, [10, 0]))
	>>> c.add_trace(buffer_from_list(types.uint8_t, [ 8, 30]))
	>>> c.add_trace(buffer_from_list(types.uint8_t, [ 6, 15]))
	>>> c.update_matrix()       #calculate the correlation
	>>> round(c.matrix[0], 2)
	1.0
	>>> round(c.matrix[1], 2)
	-0.5
	"""
	cdef size_t        count
	cdef CCorrelator * _cor
	cdef int preprocessed

	cdef Buffer        _hypo
	cdef Buffer        _matrix

	def __init__(self, samples, traces, keys):
		self._cor   = new CCorrelator(samples, traces, keys)
		self.count  = 0
		self._hypo   = _Buffer(self._cor.hypo,   keys * traces,  types.uint8_t)
		self._matrix = _Buffer(self._cor.matrix, keys * samples, types.double)
		self.preprocessed = False

	property hypo:
		def __get__(self):
			return self._hypo
	property matrix:
		def __get__(self):
			return self._matrix

	def add_trace(self, Buffer buf, int idx=-1):
		"""
		add_trace(buf, idx=-1)

		processes a trace (:class:`dpa.preprocessor.Buffer` buf) for the :class:`Correlator` by updating
		intermediate values

		if *idx* is set, the trace will be added as trace number *idx* allowing
		to add traces in arbitrary order
		"""
		if not self.preprocessed:
			raise Exception("need to call preprocess() prior to adding traces")
		if idx == -1:
			idx = self.count
			self.count += 1

		if buf.type == types.uint8_t:
			with nogil:
				self._cor.add_trace_u8(idx, <uint8_t *> buf.buf)
		elif buf.type == types.uint16_t:
			with nogil:
				self._cor.add_trace_u16(idx, <uint16_t *> buf.buf)
		elif buf.type == types.float:
			with nogil:
				self._cor.add_trace_float(idx, <float *> buf.buf)

	def preprocess(self):
		"preprocesses the hypothesis. MUST be called before adding the first trace"
		self._cor.preprocess()
		self.preprocessed = True

	def update_matrix(self):
		"updates the correlation matrix. MUST be called before accessing the matrix"
		self._cor.update_matrix()

def dump_matrix(f, m, keys, samples):
	"""
	dump a octave readable form of the :attr:`Correlator.matrix` *m* to
	the file-descriptor *f*, assuming that *m* is a *keys* x *samples* matrix
	"""
	for k in xrange(keys):
		for i in xrange(samples):
			f.write("%lf " % m[k*samples + i])
		f.write("\n")

if __name__=="__main__":
	samples =  128
	traces  =  1000
	keys    =   1
	import random
	from preprocessor import buffer_from_list
	c = Correlator(samples, traces, keys)

	#fill the hypothesis for each trace
	for i in xrange(traces):
		c.hypo[i] = 128 + random.randint(-30, 30)
	c.preprocess()
	
	#generate the traces
	for i in xrange(traces):
		trace = buffer_from_list(types.uint8_t, [c.hypo[i] + random.randint(-j, j) for j in xrange(samples)])
		c.add_trace(trace)

	#dump the matrix
	c.update_matrix()
	dump_matrix(sys.stdout, c.matrix, keys, samples)
