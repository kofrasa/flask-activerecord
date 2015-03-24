
install:
	@python setup.py install
	@make clean

test:
	@python -m unittest -v test_activerecord

clean:
	@rm -fr dist build *.egg-info *.py[cod]

.PHONY: install test clean