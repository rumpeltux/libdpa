from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

setup(
    cmdclass = {'build_ext': build_ext},
    packages=['dpa'],
    package_dir={'dpa': 'dpa'},
    ext_modules = [
	Extension("dpa.preprocessor", ["src/dpa/preprocess.c", "src/dpa/preprocessor.pyx"],
		define_macros=[('WITH_FFT', '1')], libraries=["fftw3"],
		include_dirs=['./src'],
		depends=["src/dpa/preprocess.h", "src/dpa/types.pxh", "src/dpa/buffer.pxh", "src/dpa/preprocessor.pxd"]),
	Extension("dpa.correlation", ["src/dpa/correlator.cpp", "src/dpa/correlation.pyx"],
		define_macros=[('SHARED', '1')],
		language="c++",
		depends=["src/dpa/correlator.h"])
	]
)

