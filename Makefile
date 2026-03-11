PYTHON = python
SCRIPT = ORCSystemStudy.py
REQUIREMENTS = requirements.txt

.PHONY: all install compile run clean

all: run

install:
	$(PYTHON) -m pip install -r $(REQUIREMENTS)

compile:
	$(PYTHON) -m py_compile $(SCRIPT)

run: install compile
	$(PYTHON) $(SCRIPT)

clean:
	rm -rf __pycache__
	rm -f thesis_results/ORC_run2.csv