"""Linear plugin configuration"""

from noxus_sdk.schemas import ValidationResult
from noxus_sdk.plugins import PluginConfiguration
from noxus_sdk.ncl import APIKeyField, Parameter, ConfigText


class LinearPluginConfiguration(PluginConfiguration):
    """Linear plugin configuration"""

    client_id: str = Parameter(
        description="The Client ID of your Linear app",
        display=ConfigText(label="Linear Client ID"),
    )
    client_secret: str = Parameter(
        description="The Client Secret of your Linear app",
        display=APIKeyField(label="Linear Client Secret", name="LINEAR_CLIENT_SECRET", key="LINEAR_CLIENT_SECRET"),
    )

    def validate_config(self) -> ValidationResult:
        # TODO: Think about a way to validate the config
        return ValidationResult(valid=True)
