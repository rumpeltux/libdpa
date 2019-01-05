Preprocessor
============

.. module:: dpa
The preprocessor provides a variety of functions to assist quick loading
and processing of traces.
A trace is represented by a :class:`preprocessor.Buffer` with a certain data type and
can be stored (:meth:`preprocessor.write_file`) or read (:meth:`preprocessor.load_file`)
from files on the harddrive.

The system has been designed to be more or less type-independent, allowing
to process a trace of a certain type while outputing to another data type.
This makes sense for example for the :meth:`preprocessor.integrate` function,
that often produces values that are out of range of the source data type.
Accordingly, the :meth:`preprocessor.average` function typically outputs floats,
so a precission loss will occur unless a conversion is requested.
Nearly all functions thus accept a *dst_type* parameter, that controls the output
data type and defaults to zero and is then set to the same data type as
the input data type.

To see which types have been compiled into this module run::

    $ pydoc dpa.preprocessor.types

.. automodule:: dpa.preprocessor
   :members:
