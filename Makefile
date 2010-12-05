default: modules doc

modules:
	make -C src/dpa
	python setup.py build

doc: modules
	make -C doc html

install: modules
	python setup.py install

test: modules
	PYTHONPATH="`echo build/lib*`" python examples/tests.py

clean:
	python setup.py clean
	make -C src/dpa clean
	make -C doc clean
	rm -r build || true
