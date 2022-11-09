import click


def validate_key(ctx, param, value):
    prefixes = ("test_", "live_", "access_")
    if value.startswith(prefixes):
        return value

    raise click.BadParameter(
        f"The key should start with one of: {', '.join(prefixes)}",
    )


@click.command()
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
def cli(key, testmode):
    if key.startswith("access_") and testmode:
        click.echo("Enabling testmode")


def main():
    cli(auto_envvar_prefix="MOLLIE")
