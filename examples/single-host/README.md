# Gluu Server Enterprise Edition Single-host Setup ![CDNJS](https://img.shields.io/badge/UNDERCONSTRUCTION-red.svg?style=for-the-badge)

This is an example of running Gluu Server Enterprise Edition on a single VM.

## Requirements

1)  Follow the [Docker installation instructions](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-using-the-repository) or use the [convenient installation script](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-using-the-convenience-script)

1)  Install [docker-compose](https://docs.docker.com/compose/install/#install-compose)

1)  Obtain files for deployment:

    ```
    wget https://github.com/GluuFederation/community-edition-containers/archive/4.0.0.zip \
        && unzip 4.0.0.zip
    cd community-edition-containers-4.0.0/examples/single-host
    chmod +x run_all.sh
    ```

## Pre-Installation Notes

Before deploying Gluu Server, choose whether to use default or custom installation. If default installation is selected, skip over the [Customizing Installation](#customizing-installation) section and go to [Deploying Gluu Server](#deploying-gluu-server) section instead.

## Customizing Installation

### Choosing Services

List of supported services:

| Service             | Setting Name           | Mandatory | Enabled |
| ------------------- | ---------------------- | --------- | ------- |
| `consul`            | -                      | yes       | always  |
| `registrator`       | -                      | yes       | always  |
| `vault`             | -                      | yes       | always  |
| `nginx`             | -                      | yes       | always  |
| `oxauth`            | -                      | no        | yes     |
| `oxtrust`           | -                      | no        | yes     |
| `ldap`              | `SVC_LDAP`             | no        | yes     |
| `oxpassport`        | `SVC_OXPASSPORT`       | no        | yes     |
| `oxshibboleth`      | `SVC_OXSHIBBOLETH`     | no        | yes     |
| `redis`             | `SVC_REDIS`            | no        | no      |
| `radius`            | `SVC_RADIUS`           | no        | no      |
| `couchbase`         | `SVC_COUCHBASE`        | no        | no      |
| `vault` auto-unseal | `SVC_VAULT_AUTOUNSEAL` | no        | no      |
| `oxd_server`        | `SVC_OXD_SERVER`       | no        | no      |
| `key_rotation`      | `SVC_KEY_ROTATION`     | no        | no      |
| `cr_rotate`         | `SVC_CR_ROTATE`        | no        | no      |

To enable/disable non-mandatory services listed above, create `settings.sh` (if not exist) and set the value to `"yes"` to enable or set to any value to disable the service. Here's an example:

```
#!/bin/env bash
set -e

SVC_LDAP="yes"              # will be enabled
SVC_OXPASSPORT="no"         # will be disabled
SVC_OXSHIBBOLETH=""         # will be disabled
SVC_VAULT_AUTOUNSEAL="yes"  # enable autounseal with GCP KMS API
```

If `docker-compose.override.yml` exists, this file will be added as the last Compose file. For reference on multiple Compose file, please take a look at https://docs.docker.com/compose/extends/#multiple-compose-files.

### Using Vault auto-unseal

In this example, Google Cloud Platform (GCP) KMS is going to be used. Here's an example on how to obtain [GCP KMS credentials](https://shadow-soft.com/vault-auto-unseal/) JSON file, and save it as `gcp_kms_creds.json` in the same directory where `run_all.sh` is located. Here's an example:

```
{
    "type": "service_account",
    "project_id": "project",
    "private_key_id": "1234abcd",
    "private_key": "-----BEGIN PRIVATE KEY-----\nabcdEFGH==\n-----END PRIVATE KEY-----\n",
    "client_email": "sa@project.iam.gserviceaccount.com",
    "client_id": "1234567890",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/sa%40project.iam.gserviceaccount.com"
}
```

Afterwards, create `gcp_kms_stanza.hcl` in the same directory where `run_all.sh` is located. Here's an example:

```
seal "gcpckms" {
    credentials = "/vault/config/creds.json"
    project     = "<PROJECT_NAME>"
    region      = "<REGION_NAME>"
    key_ring    = "<KEYRING_NAME>"
    crypto_key  = "<KEY_NAME>"
}
```

## Deploying Gluu Server

Run the following script:

```
./run_all.sh
```

Do not be alarmed for the `warning` alerts that may show up. Wait until it prompts for information or loads the previous configuration found. In the case where this is a fresh install, the output will be similar to the following logs:

```
./run_all.sh
[I] Determining OS Type and Attempting to Gather External IP Address
Host is detected as Linux
Is this the correct external IP Address: 172.189.222.111 [Y/n]? y
[I] Preparing cluster-wide config and secrets
WARNING: The DOMAIN variable is not set. Defaulting to a blank string.
WARNING: The HOST_IP variable is not set. Defaulting to a blank string.
Pulling consul (consul:)...
latest: Pulling from library/consul
bdf0201b3a05: Pull complete
af3d1f90fc60: Pull complete
d3a756372895: Pull complete
54efc599d7c7: Pull complete
73d2c234fe14: Pull complete
cbf8018e609a: Pull complete
Digest: sha256:bce60e9bf3e5bbbb943b13b87077635iisdksdf993579d8a6d05f2ea69bccd
Status: Downloaded newer image for consul:latest
Creating consul ... done
[I] Checking existing config in Consul
[W] Unable to get config in Consul; retrying ...
[W] Unable to get config in Consul; retrying ...
[W] Unable to get config in Consul; retrying ...
[W] Configuration not found in Consul
[I] Creating new configuration, please input the following parameters
Enter Domain:                 yourdomain
Enter Country Code:           US
Enter State:                  TX
Enter City:                   Austin
Enter Email:                  email@example.com
Enter Organization:           Gluu Inc
Enter Admin/LDAP Password:
Confirm Admin/LDAP Password:
Continue with the above settings? [Y/n]y
```

The startup process may take some time. Keep track of the deployment by using the following command:

```
./run_all.sh logs -f
```

**NOTE**: On initial deployment, since Vault has not been configured yet, the `run_all.sh` will generate root token and key to interact with Vault API, saved as `vault_key_token.txt`. Secure this file as it contains recovery key and root token.

## Tearing Down Gluu Server

Run the following command to delete all objects during the deployment:

```
./run_all.sh down
```

## Documentation

Please refer to the [Gluu Server Enterprise Edition Documentation](https://gluu.org/docs/de/4.0.0) for further reading on Docker image implementations.
