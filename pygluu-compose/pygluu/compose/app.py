"""Application to manage containers."""

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
import click_spinner
import stdiomask
from compose.cli.command import get_project
from compose.cli.command import get_config_path_from_options
from compose.cli.main import TopLevelCommand
from compose.config.config import yaml
from compose.config.environment import Environment

from .settings import DEFAULT_SETTINGS
from .settings import COMPOSE_MAPPINGS
from .version import __gluu_version__

CONFIG_DIR = "volumes/config-init/db"
EMAIL_RGX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)
PASSWD_RGX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*\W)[a-zA-Z0-9\S]{6,}$"
)


class ContainerHelper:
    """Thin wrapper to act with container.

    :param name: Service name.
    :param docker_client: An instance of Docker client.
    """

    def __init__(self, name, docker_client):
        containers = docker_client.containers(filters={'label': [
            'com.docker.compose.service=' + name,
            'com.docker.compose.project.working_dir=' + os.getcwd(),
        ]})
        if containers:
            names = containers[0]['Names']
            if names:
                # get first name of container and crop leading slash
                name = names[0][1:]

        self.name = name
        self.docker = docker_client

    def exec(self, cmd):  # noqa: A003
        """Execute command inside a running container.

        :param cmd: Command string to be executed.
        :returns: A ``tuple`` of raw output and exit code.
        """
        exec_id = self.docker.exec_create(self.name, cmd).get("Id")
        retval = self.docker.exec_start(exec_id)
        retcode = self.docker.exec_inspect(exec_id).get("ExitCode")
        return retval, retcode


class Secret:
    """Thin wrapper to interact with Vault container.

    :param docker_client: An instance of Docker client.
    """

    UNSEAL_KEY_RE = re.compile(r"^Unseal Key 1: (.+)", re.M)

    # auto-unseal uses recovery key instead of unseal key
    RECOVERY_KEY_RE = re.compile(r"^Recovery Key 1: (.+)", re.M)

    ROOT_TOKEN_RE = re.compile(r"^Initial Root Token: (.+)", re.M)

    def __init__(self, docker_client):
        self.container = ContainerHelper("vault", docker_client)

    @contextlib.contextmanager
    def login(self):
        """Log in to Vault using specific token."""
        token = self.creds["token"]
        try:
            self.container.exec("vault login {}".format(token))
            yield
        except Exception:  # noqa: B902
            raise

    @property
    def creds(self):
        """Get credentials (root token and recovery/unseal keys).

        :returns: A mapping contains of key and token credentials.
        """
        key = ""
        token = ""
        path = pathlib.Path("vault_key_token.txt")

        if path.is_file():
            txt = path.read_text()
            try:
                key = self.UNSEAL_KEY_RE.findall(txt)[0]
            except IndexError:
                key = self.RECOVERY_KEY_RE.findall(txt)[0]
            token = self.ROOT_TOKEN_RE.findall(txt)[0]
        return {"key": key, "token": token}

    def status(self):
        """Check Vault status.

        :returns: A mapping contains of data from Vault status output.
        """
        print("[I] Checking Vault status")

        status = {}
        retry = 1
        while retry <= 3:
            raw, _ = self.container.exec("vault status -format yaml")
            with contextlib.suppress(yaml.scanner.ScannerError):
                status = yaml.safe_load(raw)
                if status:
                    break

            print("[W] Unable to get seal status in Vault; retrying ...")
            retry += 1
            time.sleep(5)
        return status

    def initialize(self):
        """Initialize Vault."""
        print("[I] Initializing Vault with 1 recovery key and token")
        out, _ = self.container.exec(
            "vault operator init "
            "-key-shares=1 "
            "-key-threshold=1 "
            "-recovery-shares=1 "
            "-recovery-threshold=1",
        )

        pathlib.Path("vault_key_token.txt").write_text(out.decode())
        print("[I] Vault recovery key and root token "
              "saved to vault_key_token.txt")

    def unseal(self):
        """Run process to unseal Vault."""
        print("[I] Unsealing Vault manually")
        self.container.exec("vault operator unseal {}".format(self.creds["key"]))

    def write_policy(self):
        """Create policy required by the application."""
        policies, _ = self.container.exec("vault policy list")
        if b"gluu" in policies.splitlines():
            return

        print("[I] Creating Vault policy for Gluu")
        self.container.exec("vault policy write gluu /vault/config/policy.hcl")

    def enable_approle(self):
        """Enable Vault's AppRole authentication."""
        raw, retcode = self.container.exec("vault auth list -format yaml")

        if retcode != 0:
            print(f"[E] Unable to get auth list; reason={raw.decode()}")
            raise click.Abort()

        auth_methods = yaml.safe_load(raw)

        if "approle/" in auth_methods:
            return

        print("[I] Enabling Vault AppRole auth")

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

        role_id, _ = self.container.exec("vault read -field=role_id auth/approle/role/gluu/role-id")
        pathlib.Path("vault_role_id.txt").write_text(role_id.decode())

        secret_id, _ = self.container.exec("vault write -f -field=secret_id auth/approle/role/gluu/secret-id")
        pathlib.Path("vault_secret_id.txt").write_text(secret_id.decode())

    def setup(self):
        """Set up Vault for the application."""
        status = self.status()
        if not status["initialized"]:
            self.initialize()

        # double check status
        time.sleep(5)
        status = self.status()
        if status["sealed"]:
            self.unseal()

        time.sleep(5)
        with self.login():
            time.sleep(5)
            self.write_policy()
            time.sleep(5)
            self.enable_approle()


class Config:
    """Thin wrapper to interact with Consul container.

    :param docker_client: An instance of Docker client.
    """

    def __init__(self, docker_client):
        self.container = ContainerHelper("consul", docker_client)

    def hostname_from_backend(self):
        """Get hostname from configs backend (Consul).

        :returns: Hostname.
        """
        print("[I] Attempting to gather FQDN from Consul")

        hostname = ""
        retry = 1

        while retry <= 3:
            value, _ = self.container.exec(
                "consul kv get -http-addr=http://consul:8500 gluu/config/hostname"
            )
            if not value.startswith(b"Error"):
                hostname = value.strip().decode()
                break

            print("[W] Unable to get FQDN from Consul; retrying ...")
            retry += 1
            time.sleep(5)
        return hostname

    def hostname_from_file(self, file_):
        """Get hostname defined in a JSON file.

        :param file_: Path to JSON file.
        :returns: Hostname.
        """
        hostname = ""
        with contextlib.suppress(FileNotFoundError, json.decoder.JSONDecodeError):
            data = json.loads(pathlib.Path(file_).read_text())
            hostname = data.get("_config", {}).get("hostname", "")
        return hostname


class App:
    """Application for managing containers."""

    def __init__(self):
        self.settings = self.get_settings()

    @contextlib.contextmanager
    def top_level_cmd(self):
        """Get TopLevelCommand instance."""
        try:
            compose_files = self.get_compose_files()
            config_path = get_config_path_from_options(
                ".",
                {},
                {"COMPOSE_FILE": compose_files},
            )

            os.environ["COMPOSE_FILE"] = compose_files

            for k, v in self.settings.items():
                if isinstance(v, bool):
                    v = f"{v}".lower()
                if isinstance(v, int):
                    v = str(v)
                os.environ[k] = v

            env = Environment()
            env.update(os.environ)

            project = get_project(os.getcwd(), config_path, environment=env)
            tlc = TopLevelCommand(project)
            yield tlc
        except Exception:  # noqa: B902
            raise

    def get_settings(self):
        """Get merged settings (default and custom settings from local Python file).

        :returns: A mapping of pre-populated configs.
        """
        settings = DEFAULT_SETTINGS
        custom_settings = {}

        with contextlib.suppress(FileNotFoundError):
            path = pathlib.Path("settings.py")
            exec(compile(path.read_text(), path, "exec"), custom_settings)

        # make sure only uppercased settings are loaded
        custom_settings = {
            k: v for k, v in custom_settings.items()
            if k.isupper() and k in settings
        }

        settings.update(custom_settings)
        return settings

    def get_compose_files(self):
        """Get all enabled Compose files.

        :returns: List of Compose files as colon-separated string.
        """
        files = ["docker-compose.yml"]
        for svc, filename in COMPOSE_MAPPINGS.items():
            if all([svc in self.settings, self.settings.get(svc), os.path.isfile(filename)]):
                files.append(filename)

        # add dev override (if any)
        if self.settings.get("ENABLE_DEV_OVERRIDE", False) is True:
            dev_overrides = {"version": "2.4", "services": {}}

            for file_ in files:
                with open(file_) as f:
                    data = yaml.safe_load(f)

                for name, svc in data["services"].items():
                    if "image" not in svc:
                        continue

                    if not svc["image"].startswith("gluufederation/"):
                        continue

                    try:
                        image_name, _ = svc["image"].split(":")
                    except ValueError:
                        image_name = svc["image"]
                    finally:
                        dev_overrides["services"][name] = {"image": f"{image_name}:{__gluu_version__}_dev"}

            with open("docker-compose.dev.yml", "w") as f:
                yaml.dump(dev_overrides, f)
            files.append("docker-compose.dev.yml")

        # add custom override (if any)
        if self.settings.get("ENABLE_OVERRIDE", False) is True and os.path.isfile("docker-compose.override.yml"):
            files.append("docker-compose.override.yml")

        return ":".join(files)

    def logs(self, follow, tail, services=None):
        """View output from containers."""
        with self.top_level_cmd() as tlc:
            tlc.logs({
                "SERVICE": services or [],
                "--tail": tail,
                "--follow": follow,
                "--timestamps": False,
                "--no-color": False,
            })

    def config(self):
        """Validate and view the Compose files."""
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
        """Teardown running containers."""
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
        """Get a list of running container.

        :returns: List of running container as string.
        """
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
        """Get docker network name used by the application."""
        with self.top_level_cmd() as tlc:
            return f"{tlc.project.name}_default"

    def gather_ip(self):
        """Gather IP address.

        :returns: IP address.
        """

        def auto_detect_ip():
            # detect IP address automatically (if possible)
            ip = ""

            socket.setdefaulttimeout(30.0)

            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                ip, _ = sock.getsockname()
            return ip

        print("[I] Attempting to gather external IP address")
        ip = self.settings["HOST_IP"] or auto_detect_ip() or click.prompt("Please input the host's external IP address")

        try:
            ipaddress.ip_address(ip)
            print(f"[I] Using {ip} as external IP address")
            self.settings["HOST_IP"] = ip
        except ValueError as exc:
            print(f"[E] Cannot determine IP address; reason={exc}")
            raise click.Abort()

    def generate_params(self, file_):
        """Generate parameters required to bootstrap the application and containers.

        :returns: A mapping of pre-populated parameters.
        """

        def prompt_hostname():
            while True:
                value = click.prompt("Enter hostname", default="demoexample.gluu.org")
                if len(value.split(".")) > 2:
                    return value
                click.echo("Hostname has to be at least three domain components.")

        def prompt_country_code():
            while True:
                value = click.prompt("Enter country code", default="US")
                if len(value) == 2 and value.isupper():
                    return value
                print("Country code must use 2 uppercased characters")

        def prompt_email():
            while True:
                value = click.prompt("Enter email", default="support@demoexample.gluu.org")
                if EMAIL_RGX.match(value):
                    return value
                print("Invalid email address.")

        def prompt_password(prompt="Enter password: "):
            # FIXME: stdiomask doesn't handle CTRL+C
            while True:
                passwd = stdiomask.getpass(prompt=prompt)
                if not PASSWD_RGX.match(passwd):
                    print("Password must be at least 6 characters and include one uppercase letter, "
                          "one lowercase letter, one digit, and one special character.")
                    continue

                passwd_confirm = stdiomask.getpass(prompt="Repeat password: ")
                if passwd_confirm != passwd:
                    print("Both passwords are not equal")
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

        pathlib.Path(file_).write_text(json.dumps(params, sort_keys=True, indent=4))
        return params

    def prepare_config_secret(self):
        """Prepare configs and secrets required by the application before deploying containers."""
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
                print(f"[I] Using {self.settings['DOMAIN']} as FQDN")
                return

            cfg_file = f"{workdir}/{CONFIG_DIR}/config.json"
            gen_file = f"{workdir}/generate.json"

            hostname = config.hostname_from_file(cfg_file)
            if hostname:
                self.settings["DOMAIN"] = hostname
            else:
                if not os.path.isfile(gen_file):
                    params = self.generate_params(gen_file)
                else:
                    with open(gen_file) as f:
                        params = json.loads(f.read())
                self.settings["DOMAIN"] = params["hostname"]

            print(f"[I] Using {self.settings['DOMAIN']} as FQDN")

    def up(self):
        """Build, (re)create, start, and attach to containers for services."""
        self.check_ports()
        self.gather_ip()
        self.prepare_config_secret()
        self._up()
        self.healthcheck()

    def healthcheck(self):
        """Run healthcheck against the application.

        The process involves making request to oxTrust container periodically.
        If the request returns a success response, mark the deployment as complete.
        Otherwise, retry the healthcheck until certain threshold (currently set at 300 seconds)
        is reached and error message is thrown.
        """
        import requests
        import urllib3
        urllib3.disable_warnings()

        wait_max = 300
        wait_delay = 10

        print(
            "[I] Launching Gluu Server; to see logs on deployment process, "
            "please run 'logs -f' command on separate terminal"
        )
        with click_spinner.spinner():
            elapsed = 0
            while elapsed <= wait_max:
                with contextlib.suppress(requests.exceptions.ConnectionError):
                    req = requests.get(
                        f"https://{self.settings['HOST_IP']}/identity/restv1/health-check",
                        verify=False,
                    )
                    if req.ok:
                        print(f"\n[I] Gluu Server installed successfully; please visit https://{self.settings['DOMAIN']}")
                        return

                time.sleep(wait_delay)
                elapsed += wait_delay

            # healthcheck likely failed
            print(f"\n[W] Unable to get healthcheck status; please check the logs or visit https://{self.settings['DOMAIN']}")

    def touch_files(self):
        """Create pre-defined files in current directory."""
        files = [
            "vault_role_id.txt",
            "vault_secret_id.txt",
            "gcp_kms_stanza.hcl",
            "gcp_kms_creds.json",
            "couchbase.crt",
            "couchbase_password",
            "couchbase_superuser_password",
            "jackrabbit_admin_password",
            "sql_password",
            "sql_root_password",
            "google-credentials.json",
        ]
        for file_ in files:
            pathlib.Path(file_).touch()

    def copy_templates(self):
        """Copy pre-defined templates to current directory."""
        entries = pathlib.Path(
            os.path.join(os.path.dirname(__file__), "templates")
        )
        curdir = os.getcwd()
        for entry in entries.iterdir():
            dst = os.path.join(curdir, entry.name)
            if os.path.exists(dst):
                print(f"[W] Skipping existing {dst}")
                continue
            shutil.copy(entry, dst)
            print(f"[I] Creating new {dst}")

    def check_ports(self):
        """Check whether ports required by the application are available.

        :returns: Ports availability as boolean.
        """
        def _check(host, port):
            socket.setdefaulttimeout(30.0)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                conn = sock.connect_ex((host, port))
                if conn == 0:
                    # port is not available
                    return False
                return True

        with self.top_level_cmd() as tlc:
            ngx_svc = tlc.project.get_service("nginx")
            if ngx_svc.containers():
                return

            # published service ports must be available if nginx has not run yet
            for port in [sp.published for sp in ngx_svc.options["ports"]]:
                port_available = _check("0.0.0.0", port)
                if not port_available:
                    print(f"[W] Required port {port} is bind to another process")
                    raise click.Abort()

    def check_workdir(self):
        """Check whether current directory is a working directory.

        Current directory will be marked as working directory if there's
        ``docker-compose.yml`` under the directory.

        If ``docker-compose.yml`` file is not exist, an error will be thrown.
        """
        if not os.path.isfile("docker-compose.yml"):
            print("[E] docker-compose.yml file is not found; "
                  "make sure to run init command first")
            raise click.Abort()
