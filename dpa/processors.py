# Author: Hagen Fritsch, 2010
# Licensed under the terms of the GNU-GPL-3.0

"""
A collection of trace processors for use in a :class:`dpa.workflow.DPAWorkflow`.

A trace processor can be easily written by inheriting from :class:`TraceProcessor`:

>>> class CustomProcessor(TraceProcessor):
...     def process(trace):
...         return custom_processing_function(trace)

Further processors can be listed with::

  $ pydoc dpa.processors
"""
import math
import preprocessor
from preprocessor import types, new_buffer

class TraceProcessor(object):
	"""
	A no-op trace processor.
	
	This is a simple base class for other trace processors doing actual computations,
	that should inherit from this class and overwrite the :meth:`process` method.

	Trace processors can be chained:

	>>> a = TraceProcessor()
	>>> b = TraceProcessor()
	>>> c = a(b)

	c.process(buf) is thus equivalent to a.process(b.process(buf))
	"""
	
	max_size = 0
	min_size = -1

	def __init__(self, dst_type=types.void, ref=None, save=False, name=None):
		self.dst_type = dst_type
		self.ref = ref
		self.save = save
		self.name = name
	def process(self, trace, idx=-1):
		"processes the :class:`dpa.preprocessor.Buffer` *trace* and returns the modified version"
		return trace
	def profile(self, trace):
		"performs profiling steps (such as finding min/max values) for the :class:`dpa.preprocessor.Buffer` *trace*"
		buf = self.process(trace, idx=-1)
		if self.min_size < 0:
			self.min_size = len(buf)
		self.max_size = max(self.max_size, len(buf))
		self.min_size = min(self.min_size, len(buf))
		return buf
	def get_samples(self):
		"returns the estimated number of samples of a output trace based on the profiling phase"
		return self.max_size
	def finalize(self):
		"finishes pending tasks"
		pass
	def __call__(self, p2, **kwargs):
		return CombinedProcessor(self, p2, **kwargs)
	def __str__(self):
		return self.name if self.name else self.__class__.__name__.replace('Processor', '')

class CombinedProcessor(TraceProcessor):
	"""
	A helper class to provide the chaining functionality for a :class:`TraceProcessor`
	"""
	def __init__(self, a, b, name = None):
		self.a = a
		self.b = b
		self.ref = self.b.ref
		self.save = self.a.save
		self.name = name
	def process(self, trace, idx=-1):
		return self.a.process( self.b.process( trace, idx ), idx)
	def profile(self, trace):
		buf_a = self.a.profile( self.b.profile( trace ) ) #make sure these get profiled indepently
		return super(CombinedProcessor, self).profile( trace )
	def __str__(self):
		return self.name if self.name else "%s(%s)" % (str(self.a), str(self.b))

class AbsProcessor(TraceProcessor):
	def process(self, trace, idx=-1):
		return preprocessor.abs(trace)

#class DiffProcessor(TraceProcessor):
#	def process(self, trace, idx=-1):
#		return trace

class AvgScaleProcessor(TraceProcessor):
	def __init__(self, count, scale=1.0, **kwargs):
		self.scale = scale
		self.count = count
		super(AvgScaleProcessor, self).__init__(**kwargs)
	def process(self, trace, idx=-1):
		return preprocessor.average(trace, n=self.count, scale=self.scale, signed_scale=False, dst_type=types.float)
	def __str__(self):
		return super(AvgScaleProcessor, self).__str__() + "-%d-%d" % (self.count, self.scale)

class IntegrateProcessor(TraceProcessor):
	def __init__(self, count, **kwargs):
		self.count = count
		super(IntegrateProcessor, self).__init__(**kwargs)
	def process(self, trace, idx=-1): 
		buf = (preprocessor.integrate(trace, self.count, dst_type=self.dst_type))
		return buf
	def __str__(self):
		return super(IntegrateProcessor, self).__str__() + "-%d" % self.count

class RasterizeProcessor(TraceProcessor):
	"""
	A processor for rasterization of traces. Please consult the thesis for
	an exact description.

	Uses a pattern defined by :class:`dpa.preprocessor.Buffer` *edge* to make each
	period the same length (*period*).

	Further options can be specified:

	*trigger*
		edge-comparism threshhold that starts search for a local minimum difference
	*pause_trigger*
		number of samples to pass without a trigger match, that causes indication
		for a data pause. This can be used to align the start of traces at
		pauses in the trace
	*min_pause*
		the minimum amount of pauses that MUST occur
	*max_pause*
		the maximum amount of pauses that are allowed to occur before assuming an error
	*header_size*
		number of samples to skip from the beginning of the trace

	FIXME: there can only ever be one active configuration of this running at the same time
	"""
	def __init__(self, edge, period, trigger=150, pause_trigger=1100, min_pause=0, max_pause=0, header_size=128, **kwargs):
		preprocessor.set_raster_config(trigger, pause_trigger, min_pause, max_pause, header_size)
		self.edge = edge
		self.period = period
		super(RasterizeProcessor, self).__init__(**kwargs)
	def process(self, trace, idx=-1):
		return preprocessor.raster(trace, self.edge, self.period, dst_type=self.dst_type)

class PeakProcessor(TraceProcessor):
	"""
	Performs peak extraction on the trace.

	Peak extraction needs information on average and variance of the trace.
	The values are determined in a profiling stage.
	"""
	def __init__(self, break_length=0, break_count=0, *args, **kwargs):
		self.avgs = []
		self.vars = []
		self.break_length = break_length
		self.break_count  = break_count
		super(PeakProcessor, self).__init__(*args, **kwargs)
	def process(self, trace, idx=-1):
		return preprocessor.peak_extract(trace, self.avg, self.var,
			break_count=self.break_count, break_length=self.break_length,
			dst_type=self.dst_type)
	def profile(self, trace):
		avg, var, _min, _max = preprocessor.analyze(trace)
		self.avgs.append(avg)
		self.vars.append(math.sqrt(var))
		self.avg = sum(self.avgs) / len(self.avgs)
		self.var = sum(self.vars) / len(self.vars)
		return super(PeakProcessor, self).profile(trace)

class RectifyProcessor(TraceProcessor):
	"""
	Rectifies a trace
	"""
	def __init__(self, *args, **kwargs):
		self.avgs = []
		super(RectifyProcessor, self).__init__(*args, **kwargs)
	def process(self, trace, idx=-1):
		return preprocessor.rectify(trace, avg=self.avg, dst_type=self.dst_type)
	def profile(self, trace):
		avg, tmp, tmp, tmp = preprocessor.analyze(trace, include_variance=False)
		self.avgs.append(avg)
		self.avg = sum(self.avgs) / len(self.avgs)
		return super(RectifyProcessor, self).profile(trace)

class NormalizeProcessor(TraceProcessor):
	"""
	Normalizes trace data globally to fit a smaller data type.

	This is useful if trace data does not fit a small data type without further processing.
	The :class:`NormalizeProcessor` determines min and max values of the traces in a profiling stage
	and fits them into the new data type.

	A common application might be:

	>>> NormalizeProcessor(dst_type=types.uint8_t)
	"""
	min = -1
	max = 0
	def process(self, trace, idx=-1):
		#TODO casting to int might screw floaters. however this is an unlikely scenario
		return preprocessor.normalize(trace, min=self.min, max=self.max, dst_type=self.dst_type)
	def profile(self, trace):
		tmp, tmp, _min, _max = preprocessor.analyze(trace, include_variance=False)
		if self.min == -1: self.min = _min
		diff = _max - _min
		self.min = int(min(_min - 0.1 * diff, self.min))
		self.max = int(max(_max + 0.1 * diff, self.max))
		return super(NormalizeProcessor, self).profile(trace)

class VoidProcessor(TraceProcessor):
	"Base class for processors not producing new traces"
	pass

class AverageCountProcessor(VoidProcessor):
	"""
	Accumulates traces to create a average and variance trace

	Take an argument:

	*callback*
		a function that is called after calculation of the average
		has been finished
		
		  callback(avg, var, name)

		where *name* is the name of the referenced processor
	"""
	callback    = None
	avg_counter = None
	
	def __init__(self, callback = lambda avg, var, **kwargs: 0, **kwargs):
		self.callback = callback
		super(AverageCountProcessor, self).__init__(**kwargs)
	def process(self, trace, idx=-1):
		if self.avg_counter is None:
			self.avg_counter = preprocessor.AverageCounter(size=self.min_size, type=types.float)
		self.avg_counter.add_trace(trace, length=min(self.min_size, len(trace)))
		return trace
	def profile(self, trace):
		if self.min_size < 0:
			self.min_size = len(trace)
		self.min_size = min(self.min_size, len(trace))
	def finalize(self):
		"calculates the average and calls the *callback* function"
		avg, var = self.avg_counter.get_buf()
		self.callback(avg, var, name=str(self.ref))

	@staticmethod
	def averagize(processors, callback=None, **kwargs):
		"takes a list of processors and creates a AverageCountProcessor instance for each one"
		if callback is None: callback = AverageCountProcessor.store
		return [AverageCountProcessor(ref=p, callback=callback, **kwargs) for p in processors]

	@staticmethod
	def store(avg, var, name):
		name = "%s-%%s.dat" % name
		preprocessor.write_file(name % "avg", avg)
		preprocessor.write_file(name % "var", var)


class CorrelationProcessor(VoidProcessor):
	"""
	Adds each processed trace to the correlation module

	*correlator*
		a :class:`dpa.correlation.Correlator` instance that has already been
		initialized with hypothesis and preprocessed
	"""
	correlator = None
	def __init__(self, correlator=None, **kwargs):
		self.correlator = correlator
		super(CorrelationProcessor, self).__init__(**kwargs)
	def process(self, trace, idx=-1):
		self.correlator.add_trace(trace, idx)
	def profile(self, trace):
		self.max_size = max(self.max_size, len(trace))
	def finalize(self):
		self.correlator.update_matrix()
	def correlations(self):
		"""
		retrieves the correlations after processing finished,
		by cutting the correlation matrix into corresponding chunks
		"""
		_samples = self.get_samples()
		_keys    = len(self.correlator.matrix) / _samples
		out = []
		sizeof_double = 8
		for i in xrange(_keys):
			out.append( new_buffer(_samples, types.double,
				ptr=self.correlator.matrix.get_addr()+(i * _samples * sizeof_double)) )
		return out
	@staticmethod
	def correlize(processors, **kwargs):
		return [CorrelationProcessor(ref=p, **kwargs) for p in processors]
