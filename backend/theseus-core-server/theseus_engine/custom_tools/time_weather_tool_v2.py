
from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os
import requests
from datetime import datetime

class TimeWeatherInputV2(BaseModel):
    location: str = Field(description="The city name to get the weather for, e.g., 'Seoul' or 'London'.")

class TimeWeatherToolV2(BaseTool):
    """
    Fetches the current system time and the current weather from OpenWeatherMap for a given location.
    It reads the API key from a .env file.
    """
    name = "time_weather_tool_v2"
    description = "Fetches current time and weather, using an API key from a .env file."
    input_model = TimeWeatherInputV2
    permission_level = 1

    async def execute(self, arguments: TimeWeatherInputV2, context: ToolExecutionContext) -> ToolResult:
        load_dotenv()
        api_key = os.getenv("OPENWEATHERMAP_API_KEY")

        if not api_key:
            return ToolResult(
                output="OPENWEATHERMAP_API_KEY not found in .env file. Please use the config_writer tool to set it.",
                is_error=True
            )

        try:
            # Get weather data
            weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={arguments.location}&appid={api_key}&units=metric"
            response = requests.get(weather_url)
            response.raise_for_status()  # Raise an exception for bad status codes
            weather_data = response.json()

            # Extract weather info
            temp = weather_data['main']['temp']
            weather_desc = weather_data['weather'][0]['description']
            
            # Get current time
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            output = f"Current time: {current_time}\\nWeather in {arguments.location}: {temp}°C, {weather_desc}"
            return ToolResult(output=output)
        except requests.exceptions.RequestException as e:
            return ToolResult(output=f"Failed to retrieve weather data: {e}", is_error=True)
        except KeyError:
            return ToolResult(output=f"Could not parse weather data for '{arguments.location}'. Is the city name correct?", is_error=True)
        except Exception as e:
            return ToolResult(output=f"An unexpected error occurred: {e}", is_error=True)

