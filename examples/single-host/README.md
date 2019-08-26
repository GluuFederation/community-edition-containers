# Gluu Server Enterprise Edition Single-host Setup ![CDNJS](https://img.shields.io/badge/UNDERCONSTRUCTION-red.svg?style=for-the-badge)

This is an example of running Gluu Server Enterprise Edition on a single VM.

## Deploying Gluu Server:

1)  Follow the [Docker installation instructions](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-using-the-repository) or use the [convenient installation script](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-using-the-convenience-script)

1)  [docker-compose](https://docs.docker.com/compose/install/#install-compose).

1)  Determine which Vault unseal process fits the operation policy:

    a)  By default, this deployment doesn't use Vault [auto-unseal](https://www.vaultproject.io/docs/concepts/seal.html#auto-unseal) feature.
        If this process is selected, you can proceed to next step to obtain files for deployment.

    b)  If Vault auto-unseal is selected, choose one of the seal stanza as seen [here](https://www.vaultproject.io/docs/configuration/seal/index.html).
        In this example, Google Cloud Platform (GCP) KMS is going to be used. Here's an example on how to obtain [GCP KMS credentials](https://shadow-soft.com/vault-auto-unseal/) JSON file, and save it as `gcp_kms_creds.json`.
        Afterwards, create `gcp_kms_stanza.hcl`:

            seal "gcpckms" {
                credentials = "/vault/config/creds.json"
                project     = "<PROJECT_NAME>"
                region      = "<REGION_NAME>"
                key_ring    = "<KEYRING_NAME>"
                crypto_key  = "<KEY_NAME>"
            }

1)  Obtain files for deployment:

        wget https://github.com/GluuFederation/community-edition-containers/archive/4.0.0.zip \
            && unzip 4.0.0.zip
        cd community-edition-containers-4.0.0/examples/single-host
        chmod +x run_all.sh

    If auto-unseal is enabled:

        cp /path/to/gcp_kms_creds.json .
        cp /path/to/gcp_kms_stanza.hcl .

1)  Run the following command inside the `/path/to/docker-gluu-server/` directory and follow the prompts:

        ./run_all.sh

    Do not be alarmed for the `warning` alerts that may show up. Wait until  it prompts you for information or loads the previous configuration found. In the case where this is a fresh install you may see something like this :

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


    The startup process may take some time. You can keep track of the deployment by using the following command:

        docker-compose logs -f

__NOTE__: On initial deployment, since Vault has not been configured yet, the `run_all.sh` will generate root token and key to interact with Vault API, saved as `vault_key_token.txt`. Secure this file as it contains recovery key and root token.

## Documentation

Please refer to the [Gluu Server Enterprise Edition Documentation](https://gluu.org/docs/de/4.0.0) for further reading on Docker image implementations.
