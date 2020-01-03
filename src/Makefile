.DEFAULT_GOAL := develop

develop:
	/usr/bin/env python3 setup.py develop

zipapp:
	shiv --compressed -o pygluu-compose -p '/usr/bin/env python3' -e pygluu.compose.cli:cli . -r requirements.txt --no-cache
