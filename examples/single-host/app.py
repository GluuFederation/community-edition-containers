# -*- coding: utf-8 -*-
import contextlib
import io
import ipaddress
import json
import os
import pathlib
import re
import socket
import time

import click
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
        click.echo("[I] Checking existing config in Consul")

        hostname = ""
        retry = 1

        while retry <= 3:
            value = self.container.exec(
                f"consul kv get -http-addr=http://consul:8500 gluu/config/hostname"
            )
            if not value.startswith(b"Error"):
                hostname = value.strip().decode()
                break

            click.echo("[W] Unable to get config in Consul; retrying ...")
            retry += 1
            time.sleep(5)
        return hostname

    def hostname_from_file(self, file_):
        hostname = ""
        with contextlib.suppress(FileNotFoundError, json.decoder.JSONDecodeError):
            with open(file_) as f:
                data = json.loads(f.read())
                hostname = data.get("hostname", "")
        return hostname


class App(object):
    default_settings = {
        "HOST_IP": "",
        "DOMAIN": "",
        "ADMIN_PW": "",
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
        "PERSISTENCE_TYPE": "ldap",
        "PERSISTENCE_LDAP_MAPPING": "default",
        "PERSISTENCE_VERSION": "4.0.1_04",
        "CONFIG_INIT_VERSION": "4.0.1_04",
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
        "ENABLE_OVERRIDE": "docker-compose.override.yml",
    }

    def __init__(self):
        self.settings = self.get_settings()
        self.touch_files()

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

            env = Environment()
            env.update(os.environ)

            project = get_project(".", config_path, environment=env)
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
        ip = ""

        # detect IP address automatically (if possible)
        click.echo("[I] Determining OS type and attempting to gather external IP address")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip, _ = sock.getsockname()
        except socket.error:
            # prompt for user-inputted IP address
            click.echo("[W] Cannot determine IP address")
            ip = click.prompt("Please input the host's external IP address: ")
        finally:
            sock.close()

        if click.confirm(f"Is this the correct external IP address? {ip}", default=True, show_default=True):
            self.settings["HOST_IP"] = ip
            return

        while True:
            ip = click.prompt("Please input the host's external IP address")
            try:
                ipaddress.ip_address(ip)
                self.settings["HOST_IP"] = ip
                break
            except ValueError as exc:
                # raised if IP is invalid
                click.echo(f"[W] {exc}")

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
                value = click.prompt("Enter email", default="support@example.com")
                if EMAIL_RGX.match(value):
                    return value
                click.echo("Password must be at least 6 characters and include one uppercase letter, ")

        def prompt_password():
            while True:
                passwd = stdiomask.getpass(prompt="Enter password: ")
                if not PASSWD_RGX.match(passwd):
                    click.echo("Password must be at least 6 characters and include one uppercase letter, "
                               "one lowercase letter, one digit, and one special character.")
                    continue

                passwd_confirm = stdiomask.getpass(prompt="Repeat password: ")
                if passwd_confirm != passwd:
                    click.echo("Both passwords are not equal")
                    continue
                return passwd

        click.echo("[I] Creating new configuration, please input the following parameters")

        params = {}
        params["hostname"] = prompt_hostname()
        params["country_code"] = prompt_country_code()
        params["state"] = click.prompt("Enter state", default="TX")
        params["city"] = click.prompt("Enter city", default="Austin")
        params["admin_pw"] = prompt_password()
        params["email"] = prompt_email()
        params["org_name"] = click.prompt("Enter organization", default="Gluu")

        with open(file_, "w") as f:
            f.write(json.dumps(params, indent=4))
        return params

    def prepare_config_secret(self):
        with self.top_level_cmd() as tlc:
            if not self.ps("consul"):
                self._up(["consul"])

            if not self.ps("vault"):
                self._up(["vault"])

                secret = Secret(tlc.project.client)
                secret.setup()

            # check if config exists
            config = Config(tlc.project.client)

            hostname = config.hostname_from_backend()
            if hostname:
                self.settings["DOMAIN"] = hostname
                return

            click.echo("[W] Configuration not found in Consul")

            if os.path.isfile(f"{CONFIG_DIR}/config.json"):
                if click.confirm("Load previously saved configuration in local disk?", default=True):
                    hostname = config.hostname_from_file(f"{CONFIG_DIR}/config.json")
                    self.settings["DOMAIN"] = hostname
                    self.run_config_init()
                    return

            # prompt inputs for generating new config and secret
            if not hostname and not os.path.isfile("generate.json"):
                params = self.generate_params("generate.json")
                self.settings["DOMAIN"] = params["hostname"]

            self.run_config_init(True)

            # cleanup
            with contextlib.suppress(FileNotFoundError):
                pathlib.Path("generate.json").unlink()

    def run_config_init(self, generate=False):
        workdir = os.path.abspath(os.path.dirname(__file__))

        volumes = [
            f"{workdir}/{CONFIG_DIR}:/app/db/",
            f"{workdir}/vault_role_id.txt:/etc/certs/vault_role_id",
            f"{workdir}/vault_secret_id.txt:/etc/certs/vault_secret_id",
        ]
        if generate:
            volumes.append(f"{workdir}/generate.json:/app/db/generate.json")

        with self.top_level_cmd() as tlc:
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
                tlc.project.client.remove_container(cid, force=True)

    def up(self):
        self.gather_ip()
        self.prepare_config_secret()
        self._up()
        self.init_db_entries()
        self.healthcheck()

    def healthcheck(self):
        import requests
        import urllib3
        urllib3.disable_warnings()

        with click.progressbar(length=300,
                               show_eta=False,
                               show_percent=False,
                               fill_char=".",
                               empty_char="",
                               width=0,
                               bar_template="%(label)s %(bar)s %(info)s",
                               label="[I] Launching Gluu Server") as pbar:
            elapsed = 0
            while elapsed <= 300:
                with contextlib.suppress(requests.exceptions.ConnectionError):
                    req = requests.head(
                        f"https://{self.settings['HOST_IP']}",
                        verify=False,
                    )
                    if req.ok:
                        click.echo(f"\n[I] Gluu Server installed successfully; please visit https://{self.settings['DOMAIN']}")
                        break
                    time.sleep(5)
                    elapsed += 5
                    pbar.update(4)

    def touch_files(self):
        files = [
            "vault_role_id.txt",
            "vault_secret_id.txt",
            "gcp_kms_stanza.hcl",
            "gcp_kms_creds.json",
            "couchbase.crt",
            "couchbase_password",
            "casa.json",
        ]
        for file_ in files:
            pathlib.Path(file_).touch()

    def init_db_entries(self):
        if os.path.isfile("db_initialized"):
            return

        click.echo("[I] Adding entries to database")

        workdir = os.path.abspath(os.path.dirname(__file__))

        volumes = [
            f"{workdir}/vault_role_id.txt:/etc/certs/vault_role_id",
            f"{workdir}/vault_secret_id.txt:/etc/certs/vault_secret_id",
            f"{workdir}/couchbase.crt:/etc/certs/couchbase.crt",
            f"{workdir}/couchbase_password:/etc/gluu/conf/couchbase_password",
        ]

        with self.top_level_cmd() as tlc:
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
                pathlib.Path("db_initialized").touch()
            except Exception:
                raise
            finally:
                tlc.project.client.remove_container(cid, force=True)


@click.group()
@click.pass_context
def cli(ctx):
    ctx.obj = App()


@cli.command()
@click.pass_obj
def config(app):
    """Validate and view the Compose file
    """
    click.echo(app.config())


@cli.command()
@click.pass_obj
def down(app):
    """Stop and remove containers, networks, images, and volumes
    """
    app.down()


@cli.command()
@click.option("-f", "--follow", default=False, help="Follow log output", is_flag=True)
@click.option("--tail", default="all", help="Number of lines to show from the end of the logs for each container")
@click.argument("services", nargs=-1)
@click.pass_obj
def logs(app, follow, tail, services):
    """View output from containers
    """
    app.logs(follow, tail, services)


@cli.command()
@click.pass_obj
def up(app):
    """Create and start containers
    """
    app.up()


if __name__ == "__main__":
    cli()
