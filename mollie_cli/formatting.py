# SPDX-FileCopyrightText: 2022-present Tom Hendrikx <tom@whyscream.net>
#
# SPDX-License-Identifier: MIT
import csv
import datetime
import json
from io import StringIO

import click
from tabulate import tabulate

from .client import ClientError

FORMAT_TABLE = "table"
FORMAT_JSON = "json"
FORMAT_CSV = "csv"

ALL_FORMATS = (
    FORMAT_TABLE,
    FORMAT_JSON,
    FORMAT_CSV,
)

TABULATE_FORMAT = "fancy_grid"

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


def flatten_dict(data, key_prefix=""):
    flattened = {}
    for key, value in data.items():
        if key == "_links":
            continue

        final_key = f"{key_prefix}_{key}" if key_prefix else key

        if type(value) in [str, int, bool] or value is None:
            flattened[final_key] = value

        elif type(value) is dict:
            # Yay, recursion!
            for key, value in flatten_dict(value, final_key).items():
                flattened[key] = value

    return flattened


def csv_format_value(value):
    """Specific formatting for some CSV data types"""
    if value is None:
        return value

    try:
        # Return a datetime object and let the CSV writer emit the proper format
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        pass

    # no special handling
    return value


def format_list_result(result, resource_name, formatting):
    """Format a list result into presentable data"""
    # fetch the properties we're going to display
    try:
        properties = RESOURCES_LIST_PROPERTIES[resource_name]
    except KeyError:
        properties = RESOURCES_LIST_PROPERTIES["_default_"]

    if formatting == FORMAT_JSON:
        click.echo(json.dumps(result, indent=4))

    elif formatting == FORMAT_CSV:
        with StringIO(newline="") as csvfile:
            csvwriter = csv.writer(csvfile)

            # Force to list so it's editable
            headers = list(properties.values())
            headers_to_remove = []

            rows = []
            for obj in result:
                row = []
                for key in properties.values():
                    value = getattr(obj, key)
                    if type(value) in (str, int, bool) or value is None:
                        row.append(value)

                    elif type(value) is dict and value.keys() == ["currency", "value"]:
                        # It's an amount, let's add an exception
                        for sub_key in value.keys():
                            new_header = f"{key}_{sub_key}"
                            if new_header not in headers:
                                # Insert the new header before the original one
                                position = headers.index(key)
                                headers.insert(position, new_header)
                            row.append(value[sub_key])
                        # now remove the original header
                        headers_to_remove.append(key)

                    else:
                        # remove this key from the headers, we can't handle this value
                        headers_to_remove.append(key)
                rows.append(row)

            for header in set(headers_to_remove):
                headers.remove(header)

            # Now that we have the actual header, write it
            csvwriter.writerow(headers)
            for row in rows:
                csvwriter.writerow([csv_format_value(f) for f in row])

            click.echo(csvfile.getvalue())

    elif formatting == FORMAT_TABLE:
        # Get the properties that we want to display in list formatting

        header = properties.keys()
        table = [header]

        for item in result:
            row = [getattr(item, p) for p in properties.values()]
            table.append(row)

        tabulated = tabulate(table, tablefmt=TABULATE_FORMAT, headers="firstrow")
        click.echo(f"\nList of {resource_name}:\n")
        click.echo(tabulated)

    else:
        raise ClientError(f"Unsupported formatting: {formatting}")


def format_get_result(result, formatting):
    """Format a single item from a get call into presentable data"""
    if formatting == FORMAT_JSON:
        click.echo(json.dumps(result, indent=4))

    elif formatting == FORMAT_CSV:
        with StringIO(newline="") as csvfile:
            csvwriter = csv.writer(csvfile)
            headers = []
            row = []
            for key, value in flatten_dict(result).items():
                headers.append(key)
                row.append(csv_format_value(value))

            csvwriter.writerow(headers)
            csvwriter.writerow(row)

            click.echo(csvfile.getvalue())

    elif formatting == FORMAT_TABLE:
        table = [["Property", "Value"]]

        for key in dir(result):
            if key.startswith("_") or key.isupper():
                continue

            value = getattr(result, key)
            if not isinstance(value, (str, int, bool, dict)) and value is not None:
                continue

            table.append([key, value])

        tabulated = tabulate(table, tablefmt=TABULATE_FORMAT, headers="firstrow")
        click.echo(f"\nProperties of {result.resource} with id {result.id}:\n")
        click.echo(tabulated)

    else:
        raise ClientError(f"Unsupported formatting: {formatting}")
