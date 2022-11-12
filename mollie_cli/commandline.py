# SPDX-FileCopyrightText: 2022-present Tom Hendrikx <tom@whyscream.net>
#
# SPDX-License-Identifier: MIT
import sys
from contextlib import contextmanager

import click

from .client import APIClient, APIError, ClientError, OAuthAPIClient
from .formatting import ALL_FORMATS, format_get_result, format_list_result


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
    "--format",
    "-f",
    "formatting",  # 'format' is a Python function
    type=click.Choice(
        ALL_FORMATS,
        case_sensitive=False,
    ),
    default=ALL_FORMATS[0],
    help="Change output formatting",
    envvar="MOLLIE_FORMAT",
)
@click.pass_context
def cli(ctx, formatting):
    ctx.ensure_object(dict)
    ctx.obj["formatting"] = formatting


@cli.group()
@click.option(
    "--key",
    "-k",
    required=True,
    type=str,
    help="The Mollie API key to use for authentication",
    callback=validate_api_key,
    envvar="MOLLIE_API_KEY",
)
@click.pass_context
def apikey(ctx, key):
    """Connect to Mollie using an api key"""
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
    """Connect to Mollie using an access token"""
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
    formatting = ctx.obj["formatting"]

    with handle_client_exceptions():
        result, _ = client.get(resource_id, hint)
        format_get_result(result, formatting)


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
    formatting = ctx.obj["formatting"]

    with handle_client_exceptions():
        result, resource_name = client.list(resource, limit)
        format_list_result(result, resource_name, formatting)


apikey.add_command(list_)
token.add_command(list_)
oauth.add_command(list_)


def main():
    """Run the commandline program"""
    cli(obj={})
