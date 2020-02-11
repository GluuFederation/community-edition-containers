# Gluu Server Community Edition Single-host/Test-drive Setup ![CDNJS](https://img.shields.io/badge/UNDERCONSTRUCTION-red.svg?style=for-the-badge)

This is an example of running Gluu Server Community Edition on a single VM.

## Quickstart

1.  Install packages (depends on OS):

    - `curl`
    - `wget`
    - `python3` (Python 3.6 and above)
    - `python3-distutils` (only for Ubuntu/Debian)

1.  Install [docker](https://docs.docker.com/install/)

1.  Get `pygluu-compose` executable by following this [doc](https://github.com/GluuFederation/community-edition-containers/blob/4.1/pygluu-compose/README.md).

1.  Run the following commands to start deploying containers:

    ```sh
    ./pygluu-compose up
    ```

    Or check available commands by running:

    ```sh
    ./pygluu-compose -h
    ```

## Documentation

Please refer to https://gluu.org/docs/de/4.0/example/singlehost/ for details.
