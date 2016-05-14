libdpa
======

libdpa is a python library for analysis tasks in differential power analysis
scenarios. It assists in the initial analysis by providing simple access to
typical preprocessing tasks. It supports efficient calculation of trace
correlations for profiling or the actual execution of an attack. Processing
steps can be combined, chainend and executed in parallel by a DPAWorkflow.

The library is the result of the master thesis:
[Design of a Framework for Side-Channel-Attacks on RFID-Tags](https://itooktheredpill.irgendwo.org/2010/side-channel-analysis-on-rfid-tags/)
which contains additional information regarding background and rationale.

Key features
============
 * type indepency of traces (no matter whether `uint8_t` or `float`)
 * workflow architecture for independent execution including trace profiling
 * parallel multiprocessing
 * chainable preprocessors
 * visualization using matplotlib

Building
========
The prerequisites for building this library are:

 * a typical build environment with python
 * [cython](http://www.cython.org/) (you might need v0.13)
 * [libfftw3](http://www.fftw.org/) for fourier transformation
   (optional if setup.py is changed accordingly)
 * python-sphinx for the documentation

To build the library run:

    make

To install the library run:

    make install

To use the library without installation:

    export PYTHONPATH="$PYTHONPATH:`pwd`/`echo build/lib*`"

License
=======

libdpa is distributed under terms of the the [GNU-GPL-3.0](http://www.gnu.org/licenses/gpl.html)
