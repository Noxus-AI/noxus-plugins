import re
import json

from noxus_sdk.ncl import (
    ConfigMultiSelect,
    Parameter,
    ConfigToggle,
)
from noxus_sdk.plugins import RemoteExecutionContext
from noxus_sdk.nodes import Connector, ConfigResponse, TypeDefinition, DataType, NodeConfiguration, NodeCategory, BaseNode

from linear.client import LinearClient


class LinearIssuesReaderConfiguration(NodeConfiguration):
    team: list[dict[str, str]] | None = Parameter(
        default=None, display=ConfigMultiSelect(label="Team", values=[])
    )
    status: list[dict[str, str]] | None = Parameter(
        default=None, display=ConfigMultiSelect(label="Status", values=[])
    )
    assignee: list[dict[str, str]] | None = Parameter(
        default=None, display=ConfigMultiSelect(label="Assignee", values=[])
    )
    format_markdown: bool = Parameter(
        default=True,
        display=ConfigToggle(label="Format as Markdown"),
        description="If enabled, the issues are formatted as readable markdown. If disabled, returns raw JSON data.",
    )


class LinearIssuesReaderNode(BaseNode[LinearIssuesReaderConfiguration]):
    version = "1"
    inputs = []
    outputs = [
        Connector(
            name="issues",
            label="Issues",
            definition=TypeDefinition(data_type=DataType.str, is_list=True),
        ),
    ]

    node_name = "LinearIssuesReaderNode"
    title = "Fetch Linear issues"
    color = "#E9F6EF"
    image = "https://storage.googleapis.com/image-storage-spot-manual/logos/external-integrations/external-integrations/linear.png"
    description = "This module enables you to fetch a list of issues from Linear."
    small_description = "List Linear issues"
    category = NodeCategory.INTEGRATIONS

    integrations = {
        "linear": ["issues:read"]
    }


    @classmethod
    async def get_config(
        cls,
        ctx: RemoteExecutionContext,
        config_response: ConfigResponse,
        skip_cache: bool = False,
    ) -> ConfigResponse:

        credentials = ctx.get_integration_credentials("linear")
        client = LinearClient(credentials["access_token"])

        config_response.config["team"]["display"]["values"] = [
            {"value": a, "label": a} for a in await client.list_teams()
        ]

        teams = [v["value"] for v in config_response.config.get("team", [])]
        team = teams[0] if teams else None

        config_response.config["status"]["display"]["values"] = [
            {"value": a, "label": a} for a in await client.list_status(team=team)
        ]
        config_response.config["assignee"]["display"]["values"] = [
            {"value": a, "label": a} for a in await client.list_users()
        ]

        return config_response

    async def call(self, ctx: RemoteExecutionContext):
        credentials = ctx.get_integration_credentials("linear")
        client = LinearClient(credentials["access_token"])
        
        issues = await client.fetch_all_issues(
            team_in=(
                [l["label"] for l in self.config.team] if self.config.team else None
            ),
            status_in=(
                [l["label"] for l in self.config.status] if self.config.status else None
            ),
            assignee_in=(
                [l["label"] for l in self.config.assignee]
                if self.config.assignee
                else None
            ),
        )

        processed_issues = []
        for issue in issues:
            issue_json_str = issue.json()
            issue_data = (
                json.loads(issue_json_str)
                if isinstance(issue_json_str, str)
                else issue_json_str
            )

            if issue_data.get("description"):
                processed_description = self._process_images_in_description(
                    issue_data["description"]
                )
                issue_data["description"] = processed_description

            if self.config.format_markdown:
                markdown_issue = self._convert_to_markdown(issue_data)
                processed_issues.append(markdown_issue)
            else:
                processed_issues.append(json.dumps(issue_data, indent=2))

        await manager.register_integration_run(
            IntegrationRunEvent(
                fingerprint=ctx.get_fingerprint(),
                integration="linear",
            )
        )
        return {"issues": processed_issues}

    def _convert_to_markdown(self, issue_data: dict) -> str:
        markdown_lines = []

        field_mappings = {
            "id": "ID",
            "createdat": "Created At",
            "updatedat": "Updated At",
        }

        for key, value in issue_data.items():
            if key.lower() in field_mappings:
                formatted_key = field_mappings[key.lower()]
            else:
                formatted_key = key.replace("_", " ").title()

            if value is None:
                value = "N/A"
            elif isinstance(value, (dict, list)):
                value = str(value)
            elif isinstance(value, str) and not value.strip():
                value = "N/A"

            if key.lower() == "description" and isinstance(value, str):
                value = value.rstrip()

                has_markdown = bool(
                    re.search(
                        r"(?:^|\n)[*\-+][\s]|(?:^|\n)#{1,6}[\s]|(?:^|\n)\d+\.[\s]|\*\*.*?\*\*|__.*?__|`.*?`",
                        value,
                        re.MULTILINE,
                    )
                )

                if has_markdown:
                    markdown_lines.append(f"**{formatted_key}**:\n\n{value}")
                    markdown_lines.append("")
                else:
                    markdown_lines.append(f"**{formatted_key}**: {value}  ")
            else:
                markdown_lines.append(f"**{formatted_key}**: {value}  ")

        return "\n".join(markdown_lines)

    def _process_images_in_description(self, description: str) -> str:
        image_pattern = r"!\[([^\]]*)\]\((https://uploads\.linear\.app/[^)]+)\)"

        def replace_image(match):
            alt_text = match.group(1)
            url = match.group(2)

            if not alt_text.strip():
                alt_text = "Image"

            return f"{alt_text} ({url})"

        processed_description = re.sub(image_pattern, replace_image, description)

        return processed_description