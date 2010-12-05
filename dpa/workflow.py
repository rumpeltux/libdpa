# Author: Hagen Fritsch, 2010
# Licensed under the terms of the GNU-GPL-3.0
#-*- coding: utf-8

import math
from helpers import *
from threadpool import Pool

class DPAWorkflow:
    """
    A helper class for a complete trace analysis workflow

    Processes a set of traces in a series of analysis steps.
    Each step is executed by a trace processor. See the :mod:`dpa.processors` module for details.

    In a profiling phase, 100 input traces will be processed sequentially to
    experimentally determine boundaries and lengths (e.g. for the 
    :class:`dpa.processors.AverageCountProcessor`).
    This phase is necessary, because several processors require further information.
    For example, the :class:`dpa.processors.NormalizeProcessor` needs information
    on the minimum and maximum of each trace. However, these values need to be
    constant for the whole set of traces as the output of the processor would
    otherwise be useless. Other processors like the peak-extraction processor
    need information on traces’ average and variance which typically do not vary
    much in a set of traces.
    Therefore, such information is pre-calculated using a couple of sample traces
    in a profiling phase. This functionality is supported by respective capabilities
    of the individual processor classes.

    The number of traces to profile can be set with the *profile_size* attribute.
    A record information dictionary can be passed to the module, which contains
    information to be used by the seperate processors, but the following keys are
    also used:
    
    *errors*
       a list of trace numbers to ignore. These traces will not be read or processed

    *profile_traces*
       a list of traces that are meant to be used for additional profiling if the
       initial 100 are not sufficient

    *trace_type*
       the data type of input traces. Default: :attr:`dpa.preprocessor.types.uint8_t`

    In the actual processing phase the traces are processed in parallel using
    all available cores if the corresponding trace processors are implemented
    to release the GIL for the actual processing. This is the case for the
    preprocessing toolsuite including the correlator.

    See this source file for a more practical and thorough application of this class.

    >>> w = DPAWorkflow(count=100)
    >>> w.processors = [TraceProcessor()] # the TraceProcessor() doesn't modify anything
    >>> w.process()
    """
    profile_size = 100
    errors = []

    def __init__(self, info_dict = {}, count = None, base_path="."):
        self.record = info_dict
        self.count  = info_dict['trace_count'] if count is None else count
        self.path   = base_path
        self.processors = []

    def __iter__(self):
        _count = 0
        errors = self.record.get('errors', [])
        for i in xrange(1, self.count+len(errors)+1):
            if not i in errors:
                if _count == self.count: break
                _count += 1
                yield "%06d.dat" % i

    def path_iter(self, in_path, out_path=None):
        for i in self:
            if out_path:
                yield os.path.join(in_path, i), os.path.join(out_path, i)
            else:
                yield os.path.join(in_path, i)

#    def start(self):
#        init_record(self.record)

    def store_avg(self, avg, name=""):
        avg, var = avg.get_buf()
        save_avg(os.path.join(self.path, name + "%s.dat"), avg, var)
  
    def _profile(self):
        """
        profile the active trace set, to learn about output-lengths and limits
        this method is automatically called by :meth:`process`()
        """
        trace_type = self.record.get('trace_type', types.uint8_t)
        profile_traces = self.record.get('profile_traces', {})
        for j,f_in in enumerate(self.path_iter(self.path)):
            if j > self.profile_size and not (j+1) in profile_traces: continue
            buf = load_file(f_in, trace_type)
            for i, p in enumerate(self.processors):
                p.idx = i
                if p.ref:
                    p.res = p.profile(p.ref.res)
                else:
                    p.res = p.profile(buf)

    def process(self):
        """
        processes the active trace set

        See :class:`DPAWorkflow` for a generic overview of provided functionality.
        """
        trace_type = self.record.get('trace_type', types.uint8_t)
        out_bufs = [None for p in self.processors]

        self._profile()

        def handle((j, (f_in, f_out))):
            if j % 13 == 0: print j
            buf = load_file(f_in, trace_type)
            out = []
            for i, p in enumerate(self.processors):
                try:
                    if p.ref:
                        b = p.process(out[p.ref.idx], idx=j)
                    else:
                        b = p.process(buf, idx=j)
                except NormalizeException, e: #mark errors and report them later. we are in threading unfortunately
                    self.errors.append(j+1)
                    out.append(None)
                    continue

                out.append(b)

                if p.save:
		    print "saving file", f_out, p.save
                    write_file(f_out % str(p), b)

        p = Pool(4)
        try:
            p.map(handle, enumerate(self.path_iter(self.path, os.path.join(self.path, "%s"))))
        except Exception, e:
            p.terminate()
            print self.errors
            raise e
        print "handling"
        print self.errors
        p.terminate()

        for i, p in enumerate(self.processors):
	    p.finalize()
        
if __name__ == "__main__":
    # this is a sample workflow that reads some information about the traces to process
    # from the record_data structure in the trace_characteristics.py module
    # feel free to use or adpot this, or replace it by a static structure
    
    from trace_characteristics import record_data
    from processors import *

    record = record_data[sys.argv[1]]
    count  = int(sys.argv[2])
    path   = sys.argv[3]

    period = record['raster'].get('period', 40)
    #record['raster']['edge'] = buffer_from_list(record.get('edge_in_t', types.uint8_t), record['raster']['edge'])

    w = DPAWorkflow(record, count, base_path=path)

    #now we define the workflow
    rasterizer = TraceProcessor(save=False)
    
    #rasterize first with high accuracy
    #rasterizer = RasterizeProcessor(dst_type=types.float, save=False, **record['raster']) 
    if 'pre_raster' in record:
        rasterizer = rasterizer | record['pre_raster'] 

    #small one, reduced quantization error
    averager   = AvgScaleProcessor(count=3,       scale=256, ref=rasterizer, dst_type=types.uint16_t) 
    #big one, reduced quantization error
    averager2  = AvgScaleProcessor(count=period/4,scale=256, ref=rasterizer, dst_type=types.uint16_t) 

    peaker     = PeakProcessor()(IntegrateProcessor(count=period/6)) #alternative: peak extration
    peaker.ref = rasterizer #let the peaker work on the rasterized trace immediately
    peaker.save= False
    normalizer = NormalizeProcessor(ref=peaker, dst_type=types.uint8_t)

    w.processors = [rasterizer, averager, averager2, peaker, normalizer]
    for p in w.processors:
        p.save = False
    w.process()
