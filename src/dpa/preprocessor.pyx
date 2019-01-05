# Author: Hagen Fritsch, 2010
# Licensed under the terms of the GNU-GPL-3.0

from libc.stdlib cimport malloc, free
from stdint cimport *
from preprocess cimport *
from threading import Lock

import os, math
from warnings import warn

include "types.pxh"
types.void = 0

include "buffer.pxh"

cdef int _T(int target, int src):
	return target << 8 | src

cdef T(int target, int src=0):
	"returns the type table index for a certain type combination"
	if src == 0: src = target
	return t_map[_T(target, src)]

ctypedef struct _raster_config:
	int trigger
	int pause_trigger
	int min_pause
	int max_pause
	int header_size

cdef extern _raster_config raster_config

# begin of the actual wrapping functions

def average(Buffer buf, int n, int skip=1, double scale=1, int signed_scale=0, int dst_type=0):
	"""
	average(buf, n, skip=1, scale=1, dst_type=types.void) -> :class:`Buffer`

	average *n* samples of :class:`Buffer` *buf*,
	the result is scaled by *scale*

	*skip* is a skip-divisor. i.e. skip=2 returns every 2nd result sample

	If *signed_scale* is set, a signed scale will be performed with the value
	*signed_scale* as the virtual zero (i.e. y = (x - signed_scale) * scale + signed_scale).
	A good value for *signed_scale* is thus the average of the trace.

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	cdef l = (buf.length - n) / skip + 1
	if dst_type == 0:
		dst_type = buf.type
	cdef Buffer out = new_buffer(l, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	
	with nogil:
		fkt.average_filter(out.buf, buf.buf, buf.length, n, skip, scale, signed_scale)
	return out

def load_file(filename, int type, size_t length=0):
	"""
	load_file(filename, type, length=0) -> :class:`Buffer`

	reads a file into memory returning a :class:`Buffer`

	a non-zero *length* specifies the maximum amounts of bytes read
	"""
	if length == 0:
		length = os.stat(filename).st_size / (type & 0xf)

	cdef Buffer out = new_buffer(length, type)
	cdef _F fkt = mod[T(type)]
	cdef char* cfilename = filename
	with nogil:
		ret = fkt.load_buf(cfilename, out.buf, out.length)
	if ret == 0:
		print "load %s failed" % filename
		return None

	return out

def write_file(filename, Buffer buf, size_t length=0):
	"""
	write_file(filename, buf, length=0)

	dumps the :class:`Buffer` *buf* to a file

	a non-zero *length* specifies the maximum amounts of bytes written
	"""
	if length == 0:
		length = buf.length
	cdef _F fkt = mod[T(buf.type)]
	cdef int ret
	cdef char* cfilename = filename
	with nogil:
		ret = fkt.write_buf(cfilename, buf.buf, length)
	return ret

def filter(Buffer buf, Buffer filter_data, double scale=1, int signed_scale=0, int dst_type=0):
	"""
	filter(buf, filter_data, scale=1, dst_type=types.void) -> :class:`Buffer`

	applies a FIR filter to the :class:`Buffer` buf

	*filter_data* is a :attr:`types.int8_t` :class:`Buffer` containing the filter coefficients,
	which are automatically scaled by 1/sum(filter_data)

	The result can be scaled by *scale*.

	If *signed_scale* is set, a signed scale will be performed with the value
	*signed_scale* as the virtual zero (i.e. y = (x - signed_scale) * scale + signed_scale).
	A good value for *signed_scale* is thus the average of the trace

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if filter_data.type & 0xf != types.int8_t: #include a bypass to allow uint8_t too (but values > 127 will fail!)
		raise Exception("filter_data must be given as int8_t")
	if dst_type == 0:
		dst_type = buf.type

	cdef size_t length = buf.length - filter_data.length + 1
	cdef Buffer out = new_buffer(length, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		fkt.apply_filter(out.buf, buf.buf, buf.length, <int8_t *>filter_data.buf, filter_data.length, scale, signed_scale)
	return out

def scale(Buffer buf, double scale=1.0, int signed_scale=0, int dst_type=0):
	"""
	scale(buf, scale=1.0, signed_scale=0, dst_type=types.void) -> :class:`Buffer`

	scales buffers values by *scale* (i.e. buf[i] *= scale)

	If *signed_scale* is set, a signed scale will be performed with the value
	*signed_scale* as the virtual zero (i.e. y = (x - signed_scale) * scale + signed_scale).
	A good value for *signed_scale* is thus the average of the trace.

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = buf.type

	cdef Buffer out = new_buffer(buf.length, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		fkt.scale(buf.length, out.buf, buf.buf, signed_scale, scale)
	return out

def analyze(Buffer buf, int include_variance=True):
	"""
	analyze(buf, include_variance=True) -> (average, variance, min, max)
	
	calculates above characteristics for the :class:`Buffer` buf

	If *variance* is not needed, calculation is slightly quicker.
	"""
	cdef double avg, var=0, _min, _max
	cdef double * p_var = &var
	if not include_variance: p_var = NULL
	cdef _F fkt = mod[T(buf.type)]
	with nogil:
		fkt.analyze(buf.buf, buf.length, &avg, p_var, &_min, &_max)
	return (avg, var, _min, _max)

def peak_extract(Buffer buf, double avg=-1, double std_dev=-1, size_t break_count=0, size_t break_length=0, int dst_type=0):
	"""
	peak_extract(buf, avg=-1, std_dev=-1, break_count=0, break_length=0, dst_type=types.void) -> :class:`Buffer`

	extracts high peaks from :class:`Buffer` buf

	If *avg* and *std_dev* are not set they are calculated in an analysis phase first.

	*break_count*
		specifies the number of pause at the beginning of the trace

		If traces are not aligned in the time domain, but include a distinct pattern
		(i.e. a pause in signal), this can be used to align them.
	*break_length*
		specifies the minimum length of each pause in samples	

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = buf.type

	if avg == -1 and std_dev == -1:
		avg, var, _min, _max = analyze(buf)
		std_dev = math.sqrt(var)

	cdef size_t length = buf.length * 11 / 10 / 4 #l / 4 * 1.1
	cdef Buffer out = new_buffer(length, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		r_size = fkt.peak_extract(out.buf, buf.buf, buf.length, avg, std_dev, break_length, break_count)
	if r_size > length: #this is unlikely. if it happens, fix above calculation
		raise Exception("peak extraction exceeded reserved buffer")
	out.length = r_size #truncate buffer length
	return out

def set_raster_config(int trigger=120, int pause_trigger=1100, int min_pause=0, int max_pause=0, int header_size=128):
	raster_config.trigger = trigger
	raster_config.pause_trigger = pause_trigger
	raster_config.min_pause = min_pause
	raster_config.max_pause = max_pause
	raster_config.header_size = header_size

	#cython bug?
	#raster_config = _raster_config(trigger, pause_trigger, min_pause, max_pause, header_size)

def spline(Buffer buf, size_t size, int dst_type=0):
	"""
	spline(buf, target_size, dst_type=types.void) -> :class:`Buffer`

	linearly interpolates a :class:`Buffer` buf to fit a given length

	For reasons of efficiency this does not do averaging, if *size* is
	significantly smaller than *buf*’s size.

	spline interpolation is not yet implemented

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = buf.type
	cdef Buffer out = new_buffer(size, dst_type)
	mod[T(dst_type, buf.type)].spline(out.buf, buf.buf, size, buf.length)
	return out

def raster(Buffer buf, Buffer edge, int period, int dst_type=0):
	"""
	raster(buf, edge, period, dst_type=types.void) -> :class:`Buffer`

	aligns a given trace buf using the pattern defined by *edge*

	*edge*
	    is a buffer of the same type as buf
	*period*
	    specifies the length of a period in samples
	    each *period* in :class:`Buffer` buf is linearly interpolated to fit the length specified by *period*

	See also :meth:`raster_config` to specify advanced attributes such as trigger_values
	and expected pause intervals.

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if buf.type != edge.type:
		raise Exception("edge must have same type as buffer")
	if dst_type == 0:
		dst_type = buf.type

	cdef size_t length = int(buf.length * 1.2 + 4 * 1024) #reserve some 20% additional space, raise exception later if we fail
	cdef Buffer out = new_buffer(length, dst_type)
	cdef int ret
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		ret = fkt.raster(out.buf, buf.buf, buf.length, &out.length, period, edge.buf, edge.length)
	if ret < 0:
		raise Exception("rasterization failed with error-code %d" % ret)
	if length < out.length:
		raise Exception("Buffer Overflow, fix calculation in preprocessor.pyx")
	return out

def rectify(Buffer buf, double avg, int dst_type=0):
	"""
	rectify(buf, avg, dst_type=types.void) -> :class:`Buffer`

	rectifies a traces, by calculating the absolute difference to *avg*

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = buf.type

	cdef Buffer out = new_buffer(buf.length, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		fkt.rectify(out.buf, buf.buf, buf.length, avg)
	return out

def reorder(Buffer buf, size_t period, int dst_type=0):
	"""
	reorder(buf, period, dst_type=types.void) -> :class:`Buffer`

	reorders a rasterized :class:`Buffer` buf so that
	
	 - *period* buffers are created, each containing only one sample of each period
	   i.e. the buffer contains only the first sample of each period and so on
	 - all buffers are concatenated again

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.

	>>> reorder(buffer_from_list(types.uint8_t, [1,2,3,4,5,6,7,8,9,10,11]), 3)
	[1, 4, 7, 10, 2, 5, 8, 11, 3, 6, 9]
	>>> reorder(buffer_from_list(types.uint8_t, [1,2,3,4,5,6,7,8,9,10]), 3)
	[1, 4, 7, 10, 2, 5, 8, 3, 6, 9]
	"""
	if dst_type == 0:
		dst_type = buf.type

	cdef Buffer out = new_buffer(buf.length, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		fkt.reorder(out.buf, buf.buf, buf.length, period)
	return out

def diff(Buffer a, Buffer b, int absolute=True, int dst_type=0):
	"""
	diff(a, b, absolute=True, dst_type=types.void) -> :class:`Buffer`

	calculates abs(a[i] - b[i]) for each sample of :class:`Buffer` *a* and *b*,
	returns a new :class:`Buffer` of length min(len(a), len(b))

	If the output :class:`Buffer` type is unsigned and *absolute* is not set
	the :class:`Buffer` will be shifted by max_{datatype}/2.

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = a.type
	if a.type != b.type:
		raise Exception("both buffers must be of same type")

	cdef int length = min(a.length, b.length)
	cdef Buffer out = new_buffer(length, dst_type)
	cdef _F fkt = mod[T(dst_type, a.type)]
	with nogil:
		fkt.diff(length, out.buf, a.buf, b.buf, absolute)
	return out

def square(Buffer buf, int dst_type=0):
	"""
	square(buf, dst_type=types.void) -> :class:`Buffer`

	calculates the square of each value in :class:`Buffer` buf

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = buf.type

	cdef Buffer out = new_buffer(buf.length, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		fkt.square_buf(out.buf, buf.buf, buf.length)
	return out

def integrate(Buffer buf, int n, int dst_type=0):
	"""
	integrate(buf, n, dst_type=types.void) -> :class:`Buffer`

	builds the sum of *n* samples each

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = buf.type

	cdef Buffer out = new_buffer(buf.length - n + 1, dst_type)
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		fkt.integrate(out.buf, buf.buf, buf.length, n)
	return out

class NormalizeException(Exception):
	pass

def normalize(Buffer buf, double min=-1, double max=-1, double adjust_factor=1.2, dst_type=0):
	"""
	normalize(buf, min=NaN, max=NaN, adjust_factor=1.2, dst_type=types.void) -> :class:`Buffer`

	normalizes a trace with values in ]min, max[ to fit the whole range
	of the *dst_type*

	If *min* and *max* are not set, they will be computed from the current trace
	with a border of *adjust_factor* (e.g. [0, 1] is adjusted to [-0.2, 1.2]).

	By explicitly specifying a *dst_type* the result :class:`Buffer` is forced to this type.
	"""
	if dst_type == 0:
		dst_type = buf.type

	if min == -1 and max == -1:
		tmp, tmp, min, max = analyze(buf, variance=False)
		diff = max - min
		min = min + diff - adjust_factor * diff
		max = max - diff + adjust_factor * diff
		#std_dev = math.sqrt(var)

	cdef Buffer out = new_buffer(buf.length, dst_type)
	cdef int ret
	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		ret = fkt.normalize(out.buf, buf.buf, buf.length, min, max)
	if ret != 1:
		raise NormalizeException("sample %d (%f) exceeded min,max range %s" % (-ret, buf[-ret], (min, max)))

	return out

def fft_filter(Buffer buf, int start, int stop, dst_type=0):
	if dst_type == 0:
		dst_type = buf.type

	cdef Buffer out = new_buffer(buf.length, dst_type)
	cdef double scale = 1
	cdef double offset = 0

	cdef _F fkt = mod[T(dst_type, buf.type)]
	with nogil:
		fkt.fft_filter(out.buf, buf.buf, buf.length, start, stop, &scale, &offset)
	return out

cdef class AverageCounter:
	"""
	The :class:`AverageCounter` processes traces sequentially and calculates a
	average and variance trace based on the input traces.

	>>> a = AverageCounter(size=5, type=types.float)
	>>> a.add_trace(buffer_from_list(types.uint8_t, [0, 1, 2, 3, 4]))
	>>> a.add_trace(buffer_from_list(types.uint8_t, [2, 2, 2, 2, 2]))
	>>> len(a)
	2
	>>> avg, var = a.get_buf()
	>>> print avg
	[1.0, 1.5, 2.0, 2.5, 3.0]
	>>> print var
	[1.0, 0.25, 0.0, 0.25, 1.0]
	"""
	cdef Buffer out_sum
	cdef Buffer out_square_sum
	cdef int count
	cdef int generate_variance
	cdef object lock
	def __init__(self, size_t size, int type, int auto_type=False, int generate_variance=True):
		"""
		__init__(self, size, type, auto_type=False)

		creates an :class:`AverageCounter` instance with space for *size* samples

		If *auto_type* is set, the function will try to automatically select
		a fitting data type, based on the input :class:`Buffer` type set in *type*.
		"""
		if auto_type:
			type_size = type & 0xf
			if type_size < 8: #advance to a 8-byte sized type (uint64_t/double) if possible
				type = (type & 0x30) | 8
			else: #if values might get too big, double is a better choice
				type = types.double
		self.out_sum = new_buffer(size, type)
		self.out_square_sum = new_buffer(size, type)
		self.out_sum.zero()
		self.out_square_sum.zero()
		self.count = 0
		self.generate_variance = generate_variance
		self.lock = Lock()
	def add_trace(self, Buffer buf, int length=0):
		if length == 0:
			length = buf.length
		if length > self.out_sum.length:
			raise Exception("trace with len %d excceds averagecounter capacity of %d" % (length, self.out_sum.length))
		if length > buf.length:
			raise Exception("cannot force a buffer to be longer than it is")
		if length != self.out_sum.length:
			warn("processing incomplete trace, this may derange the result")
		cdef _F fkt = mod[T(self.out_sum.type, buf.type)]
		self.lock.acquire()
		with nogil:
			fkt.add_average(self.out_sum.buf if self.generate_variance else NULL, self.out_square_sum.buf, buf.buf, length)
		self.lock.release()
		self.count += 1

	def get_buf(self):
		"""
		get_buf() -> (avg_buf, var_buf)

		returns one float buffer for :class:`Buffer` the average and
		one for the variance of all processed traces
		"""
		avg = scale(self.out_sum, 1./self.count, dst_type=types.float)
		variance = scale(self.out_square_sum, 1./self.count, dst_type=types.float)
		variance = diff(variance, square(avg))
		return (avg, variance)
	def __len__(self):
		"returns the number of traces already processed"
		return self.count
