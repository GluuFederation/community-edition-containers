# pygluu-compose

## Prerequisites

1.  Python 3.6+.
1.  Python `pip` package.

## Installation

### Standard Python package

1.  Prepare virtual environment or system-wide setup.

1.  Install the package:

    ```
    make install
    ```

    This command will install executable called `pygluu-compose`.

### Python zipapp

1.  Install [shiv](https://shiv.readthedocs.io/) using `pip`:

    ```sh
    pip install shiv
    ```

1.  Install the package:

    ```sh
    make zipapp
    ```

    This command will install executable called `pygluu-compose.pyz`.

## Example

Refer to [this example](https://github.com/GluuFederation/community-edition-containers/tree/compose-py3/examples/single-host) for details.
