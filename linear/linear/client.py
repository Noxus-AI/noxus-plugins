import httpx
from pydantic import BaseModel, field_validator


class LinearIssue(BaseModel):
    id: str
    identifier: str
    title: str
    description: str | None
    state: str
    createdAt: str
    updatedAt: str
    priority: int
    assignee: str | None
    project: str | None

    @field_validator("state", "assignee", "project", mode="before")
    def unwrap_name_field(cls, value):
        return value.get("name") if isinstance(value, dict) else value


class LinearClient:
    def __init__(self, api_token):
        self.api_token = api_token
        self.url = "https://api.linear.app/graphql"
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }


    async def list_teams(self):
        query = """
        query {
            teams {
                nodes {
                    name
                }
            }
        }
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.url, headers=self.headers, json={"query": query}
            )
            data = response.json()
            return list(set([a["name"] for a in data["data"]["teams"]["nodes"]]))

    async def list_status(self, teams: list[str] | None = None):
        filters = []
        if teams:
            filters.append(f'team: {{ name: {{ in: ["{", ".join(teams)}"] }} }}')
        filter_ = ("(filter: {" + ", ".join(filters) + "})") if len(filters) else ""
        query = f"""
        query {{
            workflowStates{filter_} {{
                nodes {{
                    name
                }}
            }}
        }}
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.url, headers=self.headers, json={"query": query}
            )
            data = response.json()
            return list(
                set([a["name"] for a in data["data"]["workflowStates"]["nodes"]])
            )

    async def list_users(self):
        query = f"""
        query {{
            users {{
                nodes {{
                    name
                }}
            }}
        }}
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.url, headers=self.headers, json={"query": query}
            )
            data = response.json()
            return list(set([a["name"] for a in data["data"]["users"]["nodes"]]))

    async def fetch_all_issues(
        self,
        team_in: list[str] | None = None,
        team_nin: list[str] | None = None,
        status_in: list[str] | None = None,
        status_nin: list[str] | None = None,
        assignee_in: list[str] | None = None,
        assignee_nin: list[str] | None = None,
    ):
        issues = []
        cursor = None  # Start with no cursor for the first page

        filters = []
        team_filter = None
        if team_in:
            lst = ", ".join([f'"{team}"' for team in team_in])
            team_filter = f"team: {{ name: {{ in: [{lst}] }} }}"
        elif team_nin:
            lst = ", ".join([f'"{team}"' for team in team_nin])
            team_filter = f"team: {{ name: {{ nin: [{lst}] }} }}"
        if team_filter:
            filters.append(team_filter)
        status_filter = None
        if status_in:
            lst = ", ".join([f'"{status}"' for status in status_in])
            status_filter = f"state: {{ name: {{ in: [{lst}] }} }}"
        elif status_nin:
            lst = ", ".join([f'"{status}"' for status in status_nin])
            status_filter = f"state: {{ name: {{ nin: [{lst}] }} }}"
        if status_filter:
            filters.append(status_filter)

        assignee_filter = None
        if assignee_in:
            lst = ", ".join([f'"{assignee}"' for assignee in assignee_in])
            assignee_filter = f"assignee: {{ name: {{ in: [{lst}] }} }}"
        elif assignee_nin:
            lst = ", ".join([f'"{assignee}"' for assignee in assignee_nin])
            assignee_filter = f"assignee: {{ name: {{ nin: [{lst}] }} }}"
        if assignee_filter:
            filters.append(assignee_filter)

        filter_ = (", filter: {" + ", ".join(filters) + "}") if len(filters) else ""
        query = f"""
        query($after: String) {{
            issues(first: 50, after: $after, orderBy: createdAt {filter_})  {{
                nodes {{
                    id
                    identifier
                    title
                    description
                    state {{ name }}
                    createdAt
                    updatedAt
                    priority
                    assignee {{
                        id
                        name
                    }}
                    project {{
                        id
                        name
                   }}
                }}
                pageInfo {{
                    hasNextPage
                    endCursor
                }}
            }}
        }}
        """

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                variables = {"after": cursor}
                response = await client.post(
                    self.url,
                    headers=self.headers,
                    json={"query": query, "variables": variables},
                )
                data = response.json()
                issues.extend(
                    [
                        LinearIssue.model_validate(n)
                        for n in data["data"]["issues"]["nodes"]
                    ]
                )
                page_info = data["data"]["issues"]["pageInfo"]
                if not page_info["hasNextPage"]:
                    break
                cursor = page_info["endCursor"]
        return issues
