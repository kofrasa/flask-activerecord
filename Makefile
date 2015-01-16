.PHONY: install test clean

install:
	python setup.py install

test:
	python -m unittest -v test_activerecord

clean:
	rm -fr dist build *.egg-info *.py[cod]