# Gluu Server Community Edition Containers

[Gluu Server Community Edition Documentation](https://gluu.org/docs/ce/4.1)

## Quickstart

1.  Install packages (depends on OS):

    - `curl`
    - `wget`
    - `python3` (Python 3.6 and above)
    - `python3-distutils` (only for Ubuntu/Debian)

1.  Install [docker](https://docs.docker.com/install/)

1.  Get `pygluu-compose` executable by following this [doc](./pygluu-compose/README.md).

1.  Run the following commands to start deploying containers:

    ```sh
    mkdir -p examples/single-host
    cd examples/single-host
    pygluu-compose up
    ```

    Or check available commands by running:

    ```sh
    pygluu-compose -h
    ```

## Issues

If you find any issues, please post them on the customer support portal, [support.gluu.org](https://support.gluu.org).
