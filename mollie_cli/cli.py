import sys
from contextlib import contextmanager

import click

from .client import APIClient, APIError, ClientError


def validate_key(ctx, param, value):
    prefixes = ("test_", "live_", "access_")
    if value.startswith(prefixes):
        return value

    raise click.BadParameter(
        f"The key should start with one of: {', '.join(prefixes)}",
    )


def format_result(result):
    # TODO use tabulate to format the data awesome
    click.echo(result)


@contextmanager
def handle_client_exceptions():
    """Context manager that turns exceptions from the API client into errors"""
    try:
        yield
    except APIError as exc:
        click.echo(
            f"The Mollie API returned an error: {exc}",
            err=True,
        )
        sys.exit(1)
    except ClientError as exc:
        click.echo(
            f"Something went wrong while handling your command: {exc}",
            err=True,
        )
        sys.exit(1)


@click.group()
@click.version_option()
@click.option(
    "--key",
    "-k",
    required=True,
    type=str,
    help="The Mollie API key or access token to use for authentication",
    callback=validate_key,
)
@click.option(
    "--testmode",
    "-t",
    flag_value=True,
    default=False,
    help="Enable testmode when using an access token",
)
@click.pass_context
def cli(ctx, key, testmode):
    if key.startswith("access_") and testmode:
        click.echo("Enabling testmode")

    # Setup the APIClient and save it to the context
    ctx.ensure_object(dict)
    ctx.obj["client"] = APIClient(key, testmode)


@click.command()
@click.argument("resource_id")
@click.pass_context
def get(ctx, resource_id):
    """Retrieve a single item by resource ID"""
    client = ctx.obj["client"]

    with handle_client_exceptions():
        result = client.get(resource_id)

    format_result(result)


@click.command()
@click.option(
    "--limit",
    "-l",
    type=int,
    default=10,
    help="Limit the number of results",
)
@click.argument("resource")
@click.pass_context
def list_(ctx, resource, limit):
    """List items by resource name"""
    client = ctx.obj["client"]

    with handle_client_exceptions():
        result = client.list(resource, limit)

    format_result(result)


cli.add_command(get)
cli.add_command(list_, "list")


def main():
    cli(obj={}, auto_envvar_prefix="MOLLIE")
