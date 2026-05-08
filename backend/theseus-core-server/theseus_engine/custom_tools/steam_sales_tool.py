from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field
import requests

class SteamSalesToolInput(BaseModel):
    query: str = Field(description="Game name or App ID to search for on Steam.")

class SteamSalesTool(BaseTool):
    name = "steam_sales_tracker"
    description = "Searches for a Steam game by name or App ID and returns estimated sales, owners, price, and CCU using Steam and SteamSpy APIs."
    input_model = SteamSalesToolInput
    permission_level = 1
    example_queries = [
        "스팀 게임 판매량 알려줘", "게임 매출 얼마야?",
        "스팀에서 이 게임 몇 개 팔렸어?", "게임 동접자 수 확인해줘",
        "steam game sales", "how many copies sold on steam",
    ]

    async def execute(self, arguments: SteamSalesToolInput, context: ToolExecutionContext) -> ToolResult:
        query = arguments.query
        appid = None

        if query.isdigit():
            appid = int(query)
        else:
            search_url = f"https://store.steampowered.com/api/storesearch/?term={query}&l=english&cc=US"
            try:
                resp = requests.get(search_url, timeout=10)
                data = resp.json()
                if data.get("total", 0) > 0:
                    appid = data["items"][0]["id"]
            except Exception as e:
                return ToolResult(output=f"Error searching for game '{query}': {e}", is_error=True)

        if not appid:
            return ToolResult(output=f"Game '{query}' not found.", is_error=False)

        # SteamSpy
        steamspy_url = f"https://steamspy.com/api.php?request=appdetails&appid={appid}"
        try:
            spy_resp = requests.get(steamspy_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            steamspy_data = spy_resp.json()
        except Exception as e:
            return ToolResult(output=f"Error fetching SteamSpy data: {e}", is_error=True)

        # Steam API
        steam_url = f"http://store.steampowered.com/api/appdetails?appids={appid}&cc=US"
        steam_data = None
        try:
            st_resp = requests.get(steam_url, timeout=10)
            sdata = st_resp.json()
            if sdata and str(appid) in sdata and sdata[str(appid)].get("success"):
                steam_data = sdata[str(appid)]["data"]
        except Exception as e:
            pass

        name = steamspy_data.get("name", "Unknown")
        owners = steamspy_data.get("owners", "Unknown")
        ccu = steamspy_data.get("ccu", 0)

        price_str = "Unknown"
        if steam_data and not steam_data.get("is_free"):
            price_overview = steam_data.get("price_overview")
            if price_overview:
                price_str = price_overview.get("final_formatted", "Unknown")
        elif steam_data and steam_data.get("is_free"):
            price_str = "Free"

        output_str = (
            f"Game: {name} (App ID: {appid})\n"
            f"Price: {price_str}\n"
            f"Estimated Owners: {owners}\n"
            f"CCU: {ccu}\n"
        )
        return ToolResult(output=output_str)
