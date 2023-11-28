.DEFAULT_GOAL := develop

develop:
	/usr/bin/env pip install -e .

install:
	/usr/bin/env pip install .

zipapp:
	shiv --compressed -o pygluu-compose.pyz -p '/usr/bin/env python3' -e pygluu.compose.cli:cli . --no-cache --no-build-isolation
