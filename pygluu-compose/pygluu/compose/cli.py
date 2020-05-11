import click

from .app import App


@click.group(context_settings={
    "help_option_names": ["-h", "--help"],
})
@click.pass_context
def cli(ctx):
    ctx.obj = App()


@cli.command()
@click.pass_obj
def init(app):
    """Initialize working directory
    """
    app.touch_files()
    app.copy_templates()


@cli.command()
@click.pass_obj
def config(app):
    """Validate and view the Compose file
    """
    app.check_workdir()
    click.echo(app.config())


@cli.command()
@click.pass_obj
def down(app):
    """Stop and remove containers, networks, images, and volumes
    """
    app.check_workdir()
    app.down()


@cli.command()
@click.option("-f", "--follow", default=False, help="Follow log output", is_flag=True)
@click.option("--tail", default="all", help="Number of lines to show from the end of the logs for each container")
@click.argument("services", nargs=-1)
@click.pass_obj
def logs(app, follow, tail, services):
    """View output from containers
    """
    app.check_workdir()
    app.logs(follow, tail, services)


@cli.command()
@click.pass_obj
def up(app):
    """Create and start containers
    """
    app.check_workdir()
    app.up()
