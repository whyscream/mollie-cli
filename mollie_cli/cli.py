import sys
from contextlib import contextmanager

import click
from tabulate import tabulate

from .client import APIClient, APIError, ClientError, OAuthAPIClient

RESOURCES_LIST_PROPERTIES = {
    "_default_": {"ID": "id"},
    "clients": {
        "ID": "id",
        "Organization created at": "organisation_created_at",
    },
    "customers": {"ID": "id", "E-mail": "email"},
    "orders": {
        "ID": "id",
        "Amount": "amount",
        "Status": "status",
        "Paid at": "paid_at",
    },
    "payments": {
        "ID": "id",
        "Amount": "amount",
        "Status": "status",
        "Paid at": "paid_at",
    },
    "profiles": {
        "ID": "id",
        "Name": "name",
        "E-mail": "email",
        "Status": "status",
    },
    "refunds": {
        "ID": "id",
        "Amount": "amount",
        "Status": "status",
        "Description": "description",
    },
}


def validate_api_key(ctx, param, value):
    prefixes = ("test_", "live_")
    if value.startswith(prefixes):
        return value

    raise click.BadParameter(
        f"The API key should start with one of: {', '.join(prefixes)}",
    )


def validate_token(ctx, param, value):
    if value.startswith("access_"):
        return value

    raise click.BadParameter(
        "The access token should start with: access_",
    )


def format_result_list(result, resource_name):
    properties = RESOURCES_LIST_PROPERTIES.get(resource_name)
    if not properties:
        properties = RESOURCES_LIST_PROPERTIES.get("_default_")

    header = properties.keys()
    table = [header]

    for item in result:
        row = [getattr(item, p) for p in properties.values()]
        table.append(row)

    tabulated = tabulate(table, tablefmt="fancy_grid", headers="firstrow")
    click.echo(f"\nList of {resource_name}:\n")
    click.echo(tabulated)


def format_result_item(result):
    table = [["Parameter", "Value"]]
    for key in dir(result):
        if key.startswith("_") or key.isupper():
            continue
        value = getattr(result, key)
        if not isinstance(value, (str, int, bool, dict)) and value is not None:
            continue

        table.append([key, value])

    tabulated = tabulate(table, tablefmt="fancy_grid", headers="firstrow")
    click.echo(f"\nProperties of {result.resource} with id {result.id}:\n")
    click.echo(tabulated)


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
@click.pass_context
def cli(ctx):
    ctx.ensure_object(dict)


@cli.group()
@click.option(
    "--api-key",
    "-k",
    required=True,
    type=str,
    help="The Mollie API key to use for authentication",
    callback=validate_api_key,
    envvar="MOLLIE_API_KEY",
)
@click.pass_context
def apikey(ctx, key):
    """Connect to Mollie using an api key or access token"""
    ctx.obj["client"] = APIClient(key)


@cli.group()
@click.option(
    "--access-token",
    "-a",
    required=True,
    type=str,
    help="The Mollie access token to use for authentication",
    callback=validate_token,
    envvar="MOLLIE_ACCESS_TOKEN",
)
@click.option(
    "--testmode",
    "-t",
    flag_value=True,
    default=False,
    help="Enable testmode",
    envvar="MOLLIE_TESTMODE",
)
@click.pass_context
def token(ctx, access_token, testmode):
    """Connect to Mollie using an api key or access token"""
    ctx.obj["client"] = APIClient(access_token, testmode)


@cli.group()
@click.option(
    "--client-id",
    "-i",
    type=str,
    help="The Client ID of your Mollie app",
    envvar="MOLLIE_CLIENT_ID",
)
@click.option(
    "--client-secret",
    "-s",
    type=str,
    help="The Client Secret of your Mollie app",
    envvar="MOLLIE_CLIENT_SECRET",
)
@click.option(
    "--redirect-uri",
    "-u",
    type=str,
    help="The Redirect URI of your Mollie app",
)
@click.option(
    "--testmode",
    "-t",
    flag_value=True,
    default=False,
    help="Enable testmode when using an access token",
    envvar="MOLLIE_TESTMODE",
)
@click.pass_context
def oauth(ctx, client_id, client_secret, redirect_uri, testmode):
    """Connect to Mollie using OAuth2.0"""
    client = ctx.obj["client"] = OAuthAPIClient(
        client_id,
        client_secret,
        redirect_uri,
        testmode,
    )
    with handle_client_exceptions():
        # start the authorization flow
        client.oauth_authorize()


@click.command()
@click.option(
    "--hint-resource",
    "-r",
    "hint",
    type=str,
    help="Give a hint on the resource type",
)
@click.argument("resource_id")
@click.pass_context
def get(ctx, resource_id, hint):
    """Retrieve a single item by resource ID"""
    client = ctx.obj["client"]

    with handle_client_exceptions():
        result, _ = client.get(resource_id, hint)

    format_result_item(result)


apikey.add_command(get)
token.add_command(get)
oauth.add_command(get)


@click.command("list")
@click.option(
    "--limit",
    "-l",
    type=int,
    default=10,
    help="Limit the number of results",
)
@click.argument("resource")
@click.pass_context
def list_(ctx, limit, resource):
    """List items by resource name"""
    client = ctx.obj["client"]

    with handle_client_exceptions():
        result, resource_name = client.list(resource, limit)

    format_result_list(result, resource_name)


apikey.add_command(list_)
token.add_command(list_)
oauth.add_command(list_)


def main():
    cli(obj={}, auto_envvar_prefix="MOLLIE")
