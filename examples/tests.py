import unittest, doctest
import os, sys
from glob import glob

#try:	#get the live build path
#	sys.path.append(glob('build/lib*')[0])
#except: pass

from dpa import preprocessor
from dpa.preprocessor import *

t_float = types.float
t_u8    = types.uint8_t
t_u16   = types.uint16_t

t_s8    = types.int8_t

type_list = [t_u8, t_u16, t_float]

class PreprocessorTests(unittest.TestCase):
    b = {}
    #this shall not be changed. many values are hard-coded / manually computed
    #based on this array
    array = [0,1,3.5,3,4,5,6,7,8,9]

    def setUp(self):
        for t in type_list:
            self.b[t] = buffer_from_list(t, self.array)

    def compareFloatList(self, a, b, precission=2):
        for x,y in zip(a,b):
            self.assertAlmostEqual(x,y,precission)

    def test_buffer(self):
        for t in type_list:
            self.assertEqual(len(self.b[t]), len(self.array))
            if t & 0x20: #floated type
                self.assertEqual(self.array, self.b[t].as_list())
            else:
                self.assertEqual([int(j) for j in self.array], self.b[t].as_list())

    def test_average(self):
        self.assertEqual(average(self.b[t_u8], 3, skip=2).as_list(), [1,3,5,7])
        self.compareFloatList(average(self.b[t_float], len(self.array), skip=len(self.array)/2).as_list(), [4.65])
        self.compareFloatList(average(self.b[t_u8], 3, dst_type=t_float, skip=1), [4/3., 7/3., 10/3., 4.0, 5.0, 6.0, 7.0, 8.0])
        self.compareFloatList(average(self.b[t_float], 3, skip=2), [1.5, 3.5, 5, 7])

    def test_filter(self):
        filt = buffer_from_list(t_u8, [1])
        for t in type_list:
            self.b[t] = filter(self.b[t], filt)
        self.test_buffer()
        
        filt = buffer_from_list(t_u8, [0,0,0,0,0, 0,0,0,0,1])
        for t in type_list:
            self.assertEqual(filter(self.b[t], filt).as_list(), [9])

        l = [1,2,3,4,5,6,7,8,9,10]
        filt = buffer_from_list(t_u8, l)
        for t in type_list:
            self.compareFloatList(filter(self.b[t], filt).as_list(), [sum([l[i] * self.b[t][i] for i in xrange(len(l))]) / sum(l) ])

    def test_scale(self):
        for t in type_list:
            for factor in [1, 2.0, 1.5]:
                self.compareFloatList(
                    scale(self.b[t], scale=factor),
                    [int(x) if t & 0x20 == 0 else x for x in
                        [self.b[t][i] * factor for i in xrange(len(self.b[t]))]]
                    )

    def test_analyze(self):
         for t in type_list:
            buf = self.b[t]
            avg = sum(buf.as_list())/float(len(buf))
            var = 7.84 if t & 0x20 == 0 else 7.705
            self.compareFloatList([avg, var, min(buf.as_list()), max(buf.as_list())], analyze(buf))

    def test_store_file(self):
        tmp_name = "tmpfile.unittest.%x"
        for t in type_list:
            write_file(tmp_name % t, self.b[t])
        for t in type_list:
            self.b[t] = load_file(tmp_name % t, type=t)
            os.unlink(tmp_name % t)
        self.test_buffer()

    def test_raster(self):
        pattern = buffer_from_list(t_u8, [1,5,9])
        l = buffer_from_list(t_u8, [9,3,1, 1,5,9,8,6,4,3,2, 1,6,9,8,6,5,3,2, 1,5,10,7,3, 0,4,9,6,3,2, 0,7])

        set_raster_config(trigger=10, header_size=0)
        out = raster(l, pattern, 5) #, dst_type=t_float)
        self.assertEqual([1,8,7,3,2, 1,8,7,4,2, 1,5,10,7,3], out.as_list())
        
        #TODO test pause trigger and related stuff

    def test_interpolation(self):
        "tests the linear interpolation provided by spline()"

        for t in []: #type_list:
            self.assertEqual([], spline(self.b[t], 0, dst_type=t_float).as_list())
            self.assertEqual(self.b[t].as_list(), spline(self.b[t], len(self.array), dst_type=t_float).as_list())

        self.assertEqual([1,3.5,7], spline(buffer_from_list(t_float, [1,3,4,7]), 3).as_list())
        self.assertEqual([1.0,2.5,3.5,4.75,7.0], spline(buffer_from_list(t_float, [1,3,4,7]), 5).as_list())

    def test_doctest(self):
        doctest.testmod(preprocessor)
    
    def test_diff(self):
        a = buffer_from_list(t_u8, [10])
        b = buffer_from_list(t_u8, [200])
        for t, res in [(0,    (190, (10-200 + 128 + 256)%256)),
                       (t_s8, (-66, 66))]: #exceeds data type capacity
            self.assertEqual(diff(a, b, absolute=True, dst_type=t)[0], res[0])
            self.assertEqual(diff(a, b, absolute=False, dst_type=t)[0], res[1])

    def test_integrate(self):
        for t in type_list:
            buf = self.b[t]
            res = integrate(buf, len(self.array)-1).as_list()
            buf = buf.as_list()
            exp = [sum(buf)-buf[-1], sum(buf)-buf[0]]
            self.assertEqual(res, exp)

    def test_peak_extract(self):
        b = buffer_from_list(types.float, [2,4,6,8, 5,3,2,6,9, 3,1,2,5,10, 7,5,2])
        self.assertEqual(peak_extract(b).as_list(), [8,9,10])

    def test_correlation(self):
        from dpa import correlation
        doctest.testmod(correlation)
    
if __name__ == '__main__':
    unittest.main()

