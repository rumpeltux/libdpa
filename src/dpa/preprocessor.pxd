cdef class Buffer:
	cdef void * buf
	cdef size_t length
	cdef int type
	cdef int is_allocated
	cdef void init(self, void * buf, size_t length, int type)

cdef Buffer _Buffer(void * buf, size_t length, int type)
