from datetime import datetime, timezone as tz

from src.tools.base import BaseTool, ToolResult


class GetTimeTool(BaseTool):
    name = "get_time"
    description = (
        "Returns the current date and time. "
        "Use this when the user asks what time or date it is."
    )
    parameters = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "description": "Timezone name (e.g. 'UTC'). Defaults to UTC.",
            }
        },
        "required": [],
    }

    async def execute(self, timezone: str = "UTC", **_) -> ToolResult:
        now = datetime.now(tz=tz.utc)
        return ToolResult(
            success=True,
            data={
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "timezone": "UTC",
            },
        )
