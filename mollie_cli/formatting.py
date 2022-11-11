import click
from tabulate import tabulate

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


def format_list_result(result, resource_name):
    """Format a list result into presentable data"""
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


def format_get_result(result):
    """Format a single item from a get call into presentable data"""
    table = [["Property", "Value"]]
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
