
import datetime
import requests
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

# Input model for the tool
class TimeWeatherInput(BaseModel):
    location: str = Field(..., description="The city name to get the weather for, e.g., 'Seoul' or 'London'.")
    api_key: str = Field(..., description="Your OpenWeatherMap API key.")

# The tool class
class TimeWeatherTool(BaseTool):
    """
    A tool to get the current time and weather for a specified location.
    """
    name = "time_weather_tool"
    description = "Fetches the current system time and the current weather from OpenWeatherMap for a given location."
    input_model = TimeWeatherInput
    permission_level = 1 # Available to everyone

    async def execute(self, arguments: TimeWeatherInput, context: ToolExecutionContext) -> ToolResult:
        """
        Executes the tool to get the current time and weather.
        """
        import json
        location = arguments.location
        api_key = arguments.api_key

        # 1. Get the current time
        try:
            current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return ToolResult(output=f"Failed to get current time: {e}", is_error=True)

        # 2. Get the weather information
        base_url = "https://api.openweathermap.org/data/2.5/weather"
        request_params = {
            "q": location,
            "appid": api_key,
            "units": "metric"  # For Celsius
        }

        try:
            response = requests.get(base_url, params=request_params)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

            weather_data = response.json()

            # 3. Parse the weather data
            # OpenWeatherMap uses a 'cod' field for the status
            if str(weather_data.get("cod")) != "200":
                error_message = weather_data.get("message", "Unknown error from weather API.")
                return ToolResult(output=f"Weather API error: {error_message}", is_error=True)

            main_weather = weather_data.get("main", {})
            weather_desc = weather_data.get("weather", [{}])[0].get("description", "N/A")

            weather_info = {
                "location": weather_data.get("name", location),
                "temperature_celsius": main_weather.get("temp"),
                "description": weather_desc,
                "humidity_percent": main_weather.get("humidity")
            }

            # 4. Combine results and return
            combined_result = {
                "current_time": current_time_str,
                "weather": weather_info
            }
            return ToolResult(output=json.dumps(combined_result, ensure_ascii=False, indent=2))

        except requests.exceptions.HTTPError as http_err:
            # Try to get more specific error messages from the response body
            error_details = "No details available."
            try:
                error_details = response.json().get('message', error_details)
            except Exception:
                pass # Ignore if response is not json

            if response.status_code == 401:
                return ToolResult(output=f"API key is invalid. Please check your OpenWeatherMap API key. Details: {error_details}", is_error=True)
            elif response.status_code == 404:
                return ToolResult(output=f"City not found: '{location}'. Please check the location name. Details: {error_details}", is_error=True)
            else:
                return ToolResult(output=f"An HTTP error occurred: {http_err} - {error_details}", is_error=True)
        except requests.exceptions.RequestException as req_err:
            return ToolResult(output=f"A network request error occurred: {req_err}", is_error=True)
        except Exception as e:
            return ToolResult(output=f"An unexpected error occurred: {e}", is_error=True)

