# Author: Hagen Fritsch, 2010
# Licensed under the terms of the GNU-GPL-3.0

import os, sys
import math

from preprocessor import *
from ctypes import *

def gen_bandbass(length, passband, f_sample):
	"""
	generate bandpass values for a given buffer

	>>> f_start, f_stop, f_sample = 50e3, 2e6, 13.56e6*80
	>>> gen_bandpass(len(b), (f_start, f_stop), f_sample)
	"""
	N = length / 2
	f_step = f_sample / 2 / N
	return int(passband[0] / f_step), int(passband[1] / f_step)

def hw(x):
	"""
	calculate the hamming weigth of x

	>>> hw(0x8421)
	4
	"""
	out = 0
	while x > 0:
		out += x & 1
		x >>= 1
	return out

class ByteBuffer:
	"a ctypes byte array (obsolete)"
	def __init__(self, arr):
		array = c_ubyte * len(arr)
		self.arr = array(*arr)
		self._as_parameter_ = self.arr
		self.__len__ = arr.__len__


def simple_load_avg(in_path):
	"""
	loads average and variance from in_path

	where %s in in_path is replaced by 'avg' / 'var' to load
	the corresponding float buffer

	returns (avg, var)
	"""
	avg = load_file(in_path % "avg", types.float)
	var = load_file(in_path % "var", types.float)
	return avg, var

def generate_avg(files, variance=False):
	"""
	processes each file in files

	returns preprocessor.AverageCounter instance
	"""
	i = 0
	avg = None
	for f in files:
		if i % 13 == 0: print f
		i += 1
		buf = load_file(f, types.float)
		if buf:
			if avg is None:
				avg = AverageCounter(int(len(buf) * 1.2), buf.get_type(), auto_type=True, generate_variance=variance)
			avg.add_trace(buf)
	return avg

def save_avg(out_path, avg, var):
	"counterpart to load_avg"
	write_file(out_path % "avg", avg)
	write_file(out_path % "var", var)

def init_record(record):
	raster_config(record.get('trigger', 150), record.get('pause_trigger', 1100), record.get('min_pause', 0), record.get('max_pause', 0), record.get('header_size', 128))

def show(buf):
	"plots the contents of buf using matplotlib"
	from matplotlib import pyplot
	pyplot.plot(buf)
	pyplot.show()
