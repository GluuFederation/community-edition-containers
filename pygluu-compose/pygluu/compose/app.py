import contextlib
import io
import ipaddress
import json
import os
import pathlib
import re
import shutil
import socket
import time

import click
import docker.errors
import requests.exceptions
import stdiomask
from compose.cli.command import get_project
from compose.cli.command import get_config_path_from_options
from compose.cli.main import TopLevelCommand
from compose.config.config import yaml
from compose.config.environment import Environment
from docker.types import HostConfig

CONFIG_DIR = "volumes/config-init/db"


class ContainerHelper(object):
    def __init__(self, name, docker_client):
        self.name = name
        self.docker = docker_client

    def exec(self, cmd):
        exec_id = self.docker.exec_create(self.name, cmd).get("Id")
        return self.docker.exec_start(exec_id)


class Secret(object):
    UNSEAL_KEY_RE = re.compile(r"^Unseal Key 1: (.+)", re.M)
    ROOT_TOKEN_RE = re.compile(r"^Initial Root Token: (.+)", re.M)

    def __init__(self, docker_client):
        self.container = ContainerHelper("vault", docker_client)

    @contextlib.contextmanager
    def login(self):
        token = self.creds["token"]
        try:
            self.container.exec("vault login {}".format(token))
            yield
        except Exception:
            raise

    @property
    def creds(self):
        key = ""
        token = ""

        if os.path.isfile("vault_key_token.txt"):
            with open("vault_key_token.txt") as f:
                txt = f.read()
                key = self.UNSEAL_KEY_RE.findall(txt)[0]
                token = self.ROOT_TOKEN_RE.findall(txt)[0]
        return {"key": key, "token": token}

    def status(self):
        click.echo("[I] Checking Vault status")

        status = {}
        retry = 1
        while retry <= 3:
            raw = self.container.exec("vault status -format yaml")
            with contextlib.suppress(yaml.scanner.ScannerError):
                status = yaml.safe_load(raw)
                if status:
                    break

            click.echo("[W] Unable to get seal status in Vault; retrying ...")
            retry += 1
            time.sleep(5)
        return status

    def initialize(self):
        click.echo("[I] Initializing Vault with 1 recovery key and token")
        out = self.container.exec(
            "vault operator init "
            "-key-shares=1 "
            "-key-threshold=1 "
            "-recovery-shares=1 "
            "-recovery-threshold=1",
        )
        with open("vault_key_token.txt", "w") as f:
            f.write(out.decode())
            click.echo("[I] Vault recovery key and root token "
                       "saved to vault_key_token.txt")

    def unseal(self):
        click.echo("[I] Unsealing Vault manually")
        self.container.exec("vault operator unseal {}".format(self.creds["key"]))

    def write_policy(self):
        policies = self.container.exec("vault policy list").splitlines()
        if b"gluu" in policies:
            return

        click.echo("[I] Creating Vault policy for Gluu")
        self.container.exec("vault policy write gluu /vault/config/policy.hcl")

    def enable_approle(self):
        raw = self.container.exec("vault auth list -format yaml")
        auth_methods = yaml.safe_load(raw)

        if "approle/" in auth_methods:
            return

        click.echo("[I] Enabling Vault AppRole auth")

        self.container.exec("vault auth enable approle")
        self.container.exec("vault write auth/approle/role/gluu policies=gluu")
        self.container.exec(
            "vault write auth/approle/role/gluu "
            "secret_id_ttl=0 "
            "token_num_uses=0 "
            "token_ttl=20m "
            "token_max_ttl=30m "
            "secret_id_num_uses=0"
        )

        with open("vault_role_id.txt", "w") as f:
            role_id = self.container.exec("vault read -field=role_id auth/approle/role/gluu/role-id")
            f.write(role_id.decode())

        with open("vault_secret_id.txt", "w") as f:
            secret_id = self.container.exec("vault write -f -field=secret_id auth/approle/role/gluu/secret-id")
            f.write(secret_id.decode())

    def setup(self):
        status = self.status()

        if not status["initialized"]:
            self.initialize()

        if status["sealed"]:
            time.sleep(5)
            self.unseal()

        time.sleep(5)
        with self.login():
            time.sleep(5)
            self.write_policy()
            time.sleep(5)
            self.enable_approle()


class Config(object):
    def __init__(self, docker_client):
        self.container = ContainerHelper("consul", docker_client)

    def hostname_from_backend(self):
        click.echo("[I] Attempting to gather FQDN from Consul")

        hostname = ""
        retry = 1

        while retry <= 3:
            value = self.container.exec(
                f"consul kv get -http-addr=http://consul:8500 gluu/config/hostname"
            )
            if not value.startswith(b"Error"):
                hostname = value.strip().decode()
                break

            click.echo("[W] Unable to get FQDN from Consul; retrying ...")
            retry += 1
            time.sleep(5)
        return hostname

    def hostname_from_file(self, file_):
        hostname = ""
        with contextlib.suppress(FileNotFoundError, json.decoder.JSONDecodeError):
            with open(file_) as f:
                data = json.loads(f.read())
                hostname = data.get("_config", {}).get("hostname", "")
        return hostname


class App(object):
    default_settings = {
        "HOST_IP": "",
        "DOMAIN": "",
        "ADMIN_PW": "",
        "LDAP_PW": "",
        "REDIS_PW": "",
        "REDIS_URL": "redis:6379",
        "REDIS_TYPE": "STANDALONE",
        "REDIS_USE_SSL": False,
        "REDIS_SSL_TRUSTSTORE": "",
        "REDIS_SENTINEL_GROUP": "",
        "EMAIL": "",
        "ORG_NAME": "",
        "COUNTRY_CODE": "",
        "STATE": "",
        "CITY": "",
        "SVC_LDAP": True,
        "SVC_OXAUTH": True,
        "SVC_OXTRUST": True,
        "SVC_OXPASSPORT": False,
        "SVC_OXSHIBBOLETH": False,
        "SVC_CR_ROTATE": False,
        "SVC_KEY_ROTATION": False,
        "SVC_OXD_SERVER": False,
        "SVC_RADIUS": False,
        "SVC_REDIS": False,
        "SVC_VAULT_AUTOUNSEAL": False,
        "SVC_CASA": False,
        "SVC_JACKRABBIT": False,
        "PERSISTENCE_TYPE": "ldap",
        "CACHE_TYPE": "NATIVE_PERSISTENCE",
        "PERSISTENCE_LDAP_MAPPING": "default",
        "PERSISTENCE_VERSION": "4.2.0_dev",
        "CONFIG_INIT_VERSION": "4.2.0_dev",
        "COUCHBASE_USER": "admin",
        "COUCHBASE_URL": "localhost",
        "OXTRUST_API_ENABLED": False,
        "OXTRUST_API_TEST_MODE": False,
        "PASSPORT_ENABLED": False,
        "CASA_ENABLED": False,
        "RADIUS_ENABLED": False,
        "SAML_ENABLED": False,
        "SCIM_ENABLED": False,
        "SCIM_TEST_MODE": False,
        "ENABLE_OVERRIDE": False,
        "PERSISTENCE_SKIP_EXISTING": True,
        "DOCUMENT_STORE_TYPE": "LOCAL",
    }

    compose_mappings = {
        "SVC_LDAP": "svc.ldap.yml",
        "SVC_OXAUTH": "svc.oxauth.yml",
        "SVC_OXTRUST": "svc.oxtrust.yml",
        "SVC_OXPASSPORT": "svc.oxpassport.yml",
        "SVC_OXSHIBBOLETH": "svc.oxshibboleth.yml",
        "SVC_CR_ROTATE": "svc.cr_rotate.yml",
        "SVC_KEY_ROTATION": "svc.key_rotation.yml",
        "SVC_OXD_SERVER": "svc.oxd_server.yml",
        "SVC_RADIUS": "svc.radius.yml",
        "SVC_REDIS": "svc.redis.yml",
        "SVC_VAULT_AUTOUNSEAL": "svc.vault_autounseal.yml",
        "SVC_CASA": "svc.casa.yml",
        "SVC_JACKRABBIT": "svc.jackrabbit.yml",
        "ENABLE_OVERRIDE": "docker-compose.override.yml",
    }

    def __init__(self):
        self.settings = self.get_settings()

    @contextlib.contextmanager
    def top_level_cmd(self):
        try:
            compose_files = self.get_compose_files()
            config_path = get_config_path_from_options(
                ".",
                {},
                {"COMPOSE_FILE": compose_files},
            )

            os.environ["COMPOSE_FILE"] = compose_files
            os.environ["PERSISTENCE_TYPE"] = self.settings.get("PERSISTENCE_TYPE")
            os.environ["PERSISTENCE_LDAP_MAPPING"] = self.settings.get("PERSISTENCE_LDAP_MAPPING")
            os.environ["COUCHBASE_USER"] = self.settings.get("COUCHBASE_USER")
            os.environ["COUCHBASE_URL"] = self.settings.get("COUCHBASE_URL")
            os.environ["DOMAIN"] = self.settings.get("DOMAIN")
            os.environ["HOST_IP"] = self.settings.get("HOST_IP")
            os.environ["DOCUMENT_STORE_TYPE"] = self.settings.get("DOCUMENT_STORE_TYPE")

            env = Environment()
            env.update(os.environ)

            project = get_project(os.getcwd(), config_path, environment=env)
            tlc = TopLevelCommand(project)
            yield tlc
        except Exception:
            raise

    def get_settings(self):
        """Get merged settings (default and custom settings from local Python file).
        """
        settings = self.default_settings
        custom_settings = {}

        with contextlib.suppress(FileNotFoundError):
            filename = "settings.py"
            with open(filename) as f:
                exec(compile(f.read(), filename, "exec"), custom_settings)

        # make sure only uppercased settings are loaded
        custom_settings = {
            k: v for k, v in custom_settings.items()
            if k.isupper() and k in settings
        }

        settings.update(custom_settings)
        return settings

    def get_compose_files(self):
        files = ["docker-compose.yml"]
        for svc, filename in self.compose_mappings.items():
            if all([svc in self.settings, self.settings.get(svc), os.path.isfile(filename)]):
                files.append(filename)
        return ":".join(files)

    def logs(self, follow, tail, services=None):
        with self.top_level_cmd() as tlc:
            tlc.logs({
                "SERVICE": services or [],
                "--tail": tail,
                "--follow": follow,
                "--timestamps": False,
                "--no-color": False,
            })

    def config(self):
        with self.top_level_cmd() as tlc:
            tlc.config({
                "--resolve-image-digests": False,
                "--quiet": False,
                "--services": False,
                "--volumes": False,
                "--hash": None,
                "--no-interpolate": False,
            })

    def down(self):
        with self.top_level_cmd() as tlc:
            tlc.down({
                "--rmi": False,
                "--volumes": False,
                "--remove-orphans": True,
            })

    def _up(self, services=None):
        with self.top_level_cmd() as tlc:
            tlc.up({
                "SERVICE": services or [],
                "--no-deps": False,
                "--always-recreate-deps": False,
                "--abort-on-container-exit": False,
                "--remove-orphans": True,
                "--detach": True,
                "--no-recreate": False,
                "--force-recreate": False,
                "--build": False,
                "--no-build": True,
                "--scale": {},
                "--no-color": False,
                "--quiet-pull": False,
            })

    def ps(self, service):
        trap = io.StringIO()

        # suppress output of `ps` command
        with contextlib.redirect_stdout(trap):
            with self.top_level_cmd() as tlc:
                tlc.ps({
                    "--quiet": True,
                    "--services": False,
                    "--all": False,
                    "SERVICE": [service],
                })
        return trap.getvalue().strip()

    @property
    def network_name(self):
        with self.top_level_cmd() as tlc:
            return f"{tlc.project.name}_default"

    def gather_ip(self):
        """Gather IP address.
        """

        def auto_detect_ip():
            # detect IP address automatically (if possible)
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.connect(("8.8.8.8", 80))
                ip, _ = sock.getsockname()
            except socket.error:
                ip = ""
            finally:
                sock.close()
            return ip

        click.echo("[I] Attempting to gather external IP address")
        ip = self.settings["HOST_IP"] or auto_detect_ip() or click.prompt("Please input the host's external IP address")

        try:
            ipaddress.ip_address(ip)
            click.echo(f"[I] Using {ip} as external IP address")
            self.settings["HOST_IP"] = ip
        except ValueError as exc:
            click.echo(f"[E] Cannot determine IP address; reason={exc}")
            raise click.Abort()

    def generate_params(self, file_):
        EMAIL_RGX = re.compile(
            r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        )
        PASSWD_RGX = re.compile(
            r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*\W)[a-zA-Z0-9\S]{6,}$"
        )

        def prompt_hostname():
            while True:
                value = click.prompt("Enter hostname", default="demoexample.gluu.org")
                if len(value.split(".")) == 3:
                    return value
                click.echo("Hostname provided is invalid. Please enter a FQDN with the format demoexample.gluu.org")

        def prompt_country_code():
            while True:
                value = click.prompt("Enter country code", default="US")
                if len(value) == 2 and value.isupper():
                    return value
                click.echo("Country code must use 2 uppercased characters")

        def prompt_email():
            while True:
                value = click.prompt("Enter email", default="support@demoexample.gluu.org")
                if EMAIL_RGX.match(value):
                    return value
                click.echo("Invalid email address.")

        def prompt_password(prompt="Enter password: "):
            # FIXME: stdiomask doesn't handle CTRL+C
            while True:
                passwd = stdiomask.getpass(prompt=prompt)
                if not PASSWD_RGX.match(passwd):
                    click.echo("Password must be at least 6 characters and include one uppercase letter, "
                               "one lowercase letter, one digit, and one special character.")
                    continue

                passwd_confirm = stdiomask.getpass(prompt="Repeat password: ")
                if passwd_confirm != passwd:
                    click.echo("Both passwords are not equal")
                    continue
                return passwd

        params = {}
        params["hostname"] = self.settings["DOMAIN"] or prompt_hostname()
        params["country_code"] = self.settings["COUNTRY_CODE"] or prompt_country_code()
        params["state"] = self.settings["STATE"] or click.prompt("Enter state", default="TX")
        params["city"] = self.settings["CITY"] or click.prompt("Enter city", default="Austin")
        params["admin_pw"] = self.settings["ADMIN_PW"] or prompt_password("Enter oxTrust admin password: ")

        if self.settings["PERSISTENCE_TYPE"] in ("ldap", "hybrid"):
            params["ldap_pw"] = self.settings["LDAP_PW"] or prompt_password("Enter LDAP admin password: ")
        else:
            params["ldap_pw"] = params["admin_pw"]

        params["email"] = self.settings["EMAIL"] or prompt_email()
        params["org_name"] = self.settings["ORG_NAME"] or click.prompt("Enter organization", default="Gluu")

        if self.settings["CACHE_TYPE"] == "REDIS":
            params["redis_pw"] = self.settings["REDIS_PW"] or click.prompt("Enter Redis password: ", default="")

        with open(file_, "w") as f:
            f.write(json.dumps(params, sort_keys=True, indent=4))
        return params

    def prepare_config_secret(self):
        workdir = os.getcwd()

        with self.top_level_cmd() as tlc:
            if not self.ps("consul"):
                self._up(["consul"])

            if not self.ps("vault"):
                self._up(["vault"])

            secret = Secret(tlc.project.client)
            secret.setup()

            config = Config(tlc.project.client)

            hostname = config.hostname_from_backend()
            if hostname:
                self.settings["DOMAIN"] = hostname
                click.echo(f"[I] Using {self.settings['DOMAIN']} as FQDN")
                return

            cfg_file = f"{workdir}/{CONFIG_DIR}/config.json"
            gen_file = f"{workdir}/generate.json"

            hostname = config.hostname_from_file(cfg_file)
            if hostname:
                self.settings["DOMAIN"] = hostname
            else:
                params = self.generate_params(gen_file)
                self.settings["DOMAIN"] = params["hostname"]

            click.echo(f"[I] Using {self.settings['DOMAIN']} as FQDN")
            self.run_config_init()

            # cleanup
            with contextlib.suppress(FileNotFoundError):
                pathlib.Path(gen_file).unlink()

    def run_config_init(self):
        workdir = os.getcwd()
        image = f"gluufederation/config-init:{self.settings['CONFIG_INIT_VERSION']}"

        volumes = [
            f"{workdir}/{CONFIG_DIR}:/app/db/",
            f"{workdir}/vault_role_id.txt:/etc/certs/vault_role_id",
            f"{workdir}/vault_secret_id.txt:/etc/certs/vault_secret_id",
        ]

        gen_file = f"{workdir}/generate.json"
        if os.path.isfile(gen_file):
            volumes.append(f"{gen_file}:/app/db/generate.json")

        with self.top_level_cmd() as tlc:
            retry = 0
            while retry < 3:
                try:
                    if not tlc.project.client.images(name=image):
                        click.echo(f"{self.settings['CONFIG_INIT_VERSION']}: Pulling from gluufederation/config-init")
                        tlc.project.client.pull(image)
                        break
                except (requests.exceptions.Timeout, docker.errors.APIError) as exc:
                    click.echo(f"[W] Unable to get {image}; reason={exc}; "
                               "retrying in 10 seconds")
                time.sleep(10)
                retry += 1

            cid = None
            try:
                cid = tlc.project.client.create_container(
                    image=f"gluufederation/config-init:{self.settings['CONFIG_INIT_VERSION']}",
                    name="config-init",
                    command="load",
                    environment={
                        "GLUU_CONFIG_CONSUL_HOST": "consul",
                        "GLUU_SECRET_VAULT_HOST": "vault",
                    },
                    host_config=HostConfig(
                        version="1.25",
                        network_mode=self.network_name,
                        binds=volumes,
                    ),
                ).get("Id")

                tlc.project.client.start(cid)
                for log in tlc.project.client.logs(cid, stream=True):
                    click.echo(log.strip())
            except Exception:
                raise
            finally:
                if cid:
                    tlc.project.client.remove_container(cid, force=True)

    def up(self):
        self.check_ports()
        self.gather_ip()
        self.prepare_config_secret()
        self._up()
        self.run_persistence()
        self.healthcheck()

    def healthcheck(self):
        import requests
        import urllib3
        urllib3.disable_warnings()

        wait_max = 300
        wait_delay = 10

        with click.progressbar(length=wait_max, show_eta=False, show_percent=False,
                               fill_char=".", empty_char="", width=0,
                               bar_template="%(label)s %(bar)s %(info)s",
                               label="[I] Launching Gluu Server") as pbar:
            elapsed = 0
            while elapsed <= wait_max:
                with contextlib.suppress(requests.exceptions.ConnectionError):
                    req = requests.get(
                        f"https://{self.settings['HOST_IP']}/identity/restv1/scim-configuration",
                        verify=False,
                    )
                    if req.ok:
                        click.echo(f"\n[I] Gluu Server installed successfully; please visit https://{self.settings['DOMAIN']}")
                        break
                time.sleep(wait_delay)
                elapsed += wait_delay
                pbar.update(4)

    def touch_files(self):
        files = [
            "vault_role_id.txt",
            "vault_secret_id.txt",
            "gcp_kms_stanza.hcl",
            "gcp_kms_creds.json",
            "couchbase.crt",
            "couchbase_password",
            # "casa.json",
        ]
        for file_ in files:
            pathlib.Path(file_).touch()

    def copy_templates(self):
        entries = pathlib.Path(
            os.path.join(os.path.dirname(__file__), "templates")
        )
        curdir = os.getcwd()
        for entry in entries.iterdir():
            dst = os.path.join(curdir, entry.name)
            if os.path.exists(dst):
                continue
            shutil.copy(entry, dst)

    def run_persistence(self):
        workdir = os.getcwd()

        click.echo("[I] Checking entries in persistence")

        workdir = os.getcwd()
        image = f"gluufederation/persistence:{self.settings['PERSISTENCE_VERSION']}"

        volumes = [
            f"{workdir}/vault_role_id.txt:/etc/certs/vault_role_id",
            f"{workdir}/vault_secret_id.txt:/etc/certs/vault_secret_id",
            f"{workdir}/couchbase.crt:/etc/certs/couchbase.crt",
            f"{workdir}/couchbase_password:/etc/gluu/conf/couchbase_password",
        ]

        with self.top_level_cmd() as tlc:
            retry = 0
            while retry < 3:
                try:
                    if not tlc.project.client.images(name=image):
                        click.echo(f"{self.settings['PERSISTENCE_VERSION']}: Pulling from gluufederation/persistence")
                        tlc.project.client.pull(image)
                        break
                except (requests.exceptions.Timeout, docker.errors.APIError) as exc:
                    click.echo(f"[W] Unable to get {image}; reason={exc}; "
                               "retrying in 10 seconds")
                time.sleep(10)
                retry += 1

            cid = None
            try:
                cid = tlc.project.client.create_container(
                    image=f"gluufederation/persistence:{self.settings['PERSISTENCE_VERSION']}",
                    name="persistence",
                    environment={
                        "GLUU_CONFIG_CONSUL_HOST": "consul",
                        "GLUU_SECRET_VAULT_HOST": "vault",
                        "GLUU_PERSISTENCE_TYPE": self.settings["PERSISTENCE_TYPE"],
                        "GLUU_PERSISTENCE_LDAP_MAPPING": self.settings["PERSISTENCE_LDAP_MAPPING"],
                        "GLUU_LDAP_URL": "ldap:1636",
                        "GLUU_COUCHBASE_URL": self.settings["COUCHBASE_URL"],
                        "GLUU_COUCHBASE_USER": self.settings["COUCHBASE_USER"],
                        "GLUU_OXTRUST_API_ENABLED": self.settings["OXTRUST_API_ENABLED"],
                        "GLUU_OXTRUST_API_TEST_MODE": self.settings["OXTRUST_API_TEST_MODE"],
                        "GLUU_PASSPORT_ENABLED": self.settings["PASSPORT_ENABLED"],
                        "GLUU_CASA_ENABLED": self.settings["CASA_ENABLED"],
                        "GLUU_RADIUS_ENABLED": self.settings["RADIUS_ENABLED"],
                        "GLUU_SAML_ENABLED": self.settings["SAML_ENABLED"],
                        "GLUU_SCIM_ENABLED": self.settings["SCIM_ENABLED"],
                        "GLUU_SCIM_TEST_MODE": self.settings["SCIM_TEST_MODE"],
                        "GLUU_PERSISTENCE_SKIP_EXISTING": self.settings["PERSISTENCE_SKIP_EXISTING"],
                        "GLUU_CACHE_TYPE": self.settings["CACHE_TYPE"],
                        "GLUU_REDIS_URL": self.settings["REDIS_URL"],
                        "GLUU_REDIS_TYPE": self.settings["REDIS_TYPE"],
                        "GLUU_REDIS_USE_SSL": self.settings["REDIS_USE_SSL"],
                        "GLUU_REDIS_SSL_TRUSTSTORE": self.settings["REDIS_SSL_TRUSTSTORE"],
                        "GLUU_REDIS_SENTINEL_GROUP": self.settings["REDIS_SENTINEL_GROUP"],
                        "GLUU_DOCUMENT_STORE_TYPE": self.settings["DOCUMENT_STORE_TYPE"],
                        "GLUU_JCA_RMI_URL": "http://jackrabbit:8080/rmi",
                    },
                    host_config=HostConfig(
                        version="1.25",
                        network_mode=self.network_name,
                        binds=volumes,
                    ),
                ).get("Id")

                tlc.project.client.start(cid)
                for log in tlc.project.client.logs(cid, stream=True):
                    click.echo(log.strip())
            except Exception:
                raise
            finally:
                if cid:
                    tlc.project.client.remove_container(cid, force=True)

    def check_ports(self):
        def _check(host, port):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                conn = sock.connect_ex((host, port))
                if conn == 0:
                    # port is not available
                    return False
                return True

        with self.top_level_cmd() as tlc:
            ngx_run = tlc.project.client.containers(
                filters={"name": "nginx"}
            )
            if ngx_run:
                return

            # ports 80 and 443 must available if nginx has not run yet
            for port in [80, 443]:
                port_available = _check("0.0.0.0", port)
                if not port_available:
                    click.echo(f"[W] Required port {port} is bind to another process")
                    raise click.Abort()

    def check_workdir(self):
        if not os.path.isfile("docker-compose.yml"):
            click.echo("[E] docker-compose.yml file is not found; "
                       "make sure to run init command first")
            raise click.Abort()
