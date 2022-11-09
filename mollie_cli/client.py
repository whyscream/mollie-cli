from mollie.api.client import Client as MollieClient
from mollie.api.error import Error as NativeMollieError


class APIError(Exception):
    """An error has ocurred while talking to the API."""

    pass


class ClientError(Exception):
    """Something went wrong in our Client."""

    pass


class APIClient:
    def __init__(self, key, testmode):
        self._client = self.configure_client(key)
        self._testmode = testmode

    def use_testmode(self):
        return self._uses_access_token and self._testmode

    def get_params(self, **params):
        if self.use_testmode():
            params.update({"testmode": "true"})
        return params

    def configure_client(self, key):
        client = MollieClient()
        if key.startswith(("test_", "live_")):
            client.set_api_key(key)
            self._uses_access_token = True
        elif key.startswith("access_"):
            client.set_access_token(key)
            self._uses_access_token = True
        else:
            raise RuntimeError("We don't support this type of key")

        return client

    def list(self, resource_name, limit):
        """List resources by"""
        map_ = self.get_supported_resources_map()

        if resource_name in map_.keys():
            # Found a direct match
            pass
        else:
            # Try to match a substring
            resources = [x for x in map_.keys() if x.startswith(resource_name)]
            if not resources:
                raise ClientError(f"No resource with name '{resource_name}'")
            elif len(resources) > 1:
                raise ClientError(
                    "Incomplete resource name matches multiple resources: "
                    f"{', '.join(resources)}",
                )
            else:
                resource_name = resources[0]

        resource = getattr(self._client, resource_name)
        params = self.get_params(limit=limit)
        try:
            result = resource.list(**params)
        except NativeMollieError as exc:
            raise APIError(exc) from exc
        except AttributeError:
            raise ClientError(
                f"Resource '{resource_name}' doesn't support listing"
            )  # noqa: E501

        return result, resource_name

    def get(self, resource_id):
        map_ = self.get_supported_resources_map()

        resource = None
        for resource_name, prefix in map_.items():
            if resource_id.startswith(prefix):
                resource = getattr(self._client, resource_name)
                break

        if not resource:
            raise ClientError(
                f"Cannot find a resource for id '{resource_id}'",
            )

        params = self.get_params()
        try:
            result = resource.get(resource_id, **params)
        except NativeMollieError as exc:
            raise APIError(exc) from exc
        except AttributeError:
            raise ClientError(
                f"Resource '{resource_name}' doesn't support getting single objects",  # noqa: E501
            )

        return result, resource_name

    def get_supported_resources_map(self):
        """Generate a map of resource names and prefixes."""
        resources = {}
        for attrname in dir(self._client):
            attr = getattr(self._client, attrname)
            try:
                prefix = getattr(attr, "RESOURCE_ID_PREFIX")
                if prefix:
                    resources[attrname] = prefix
            except AttributeError:
                pass

        return resources
