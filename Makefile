.PHONY: test validate check release clean

test:
	python3 -m unittest discover -s tests -v

validate:
	python3 scripts/validate_package.py

check: test validate

release: check
	python3 scripts/create_release.py

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf dist
