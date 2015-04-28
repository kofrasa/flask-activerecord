
install:
	@python setup.py install
	@make clean

test:
	@python -m unittest -v test_activerecord

clean:
	@rm -fr dist build *.egg-info *.py[cod]

upload:
	@python setup.py sdist upload -r pypi
	@make clean

.PHONY: install test clean upload
