.DEFAULT_GOAL := develop

develop:
	/usr/bin/env python3 setup.py develop

install:
	/usr/bin/env python3 setup.py install

zipapp:
	shiv --compressed -o pygluu-compose.pyz -p '/usr/bin/env python3' -e pygluu.compose.cli:cli . -r requirements.txt --no-cache --use-feature=2020-resolver
