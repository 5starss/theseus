
import os.path
import datetime as dt

from pydantic import BaseModel, Field
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from openharness.tools.base import BaseTool, ToolResult, ToolExecutionContext

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]


class GoogleCalendarToolInput(BaseModel):
    action: str = Field(..., description="The action to perform. One of 'list', 'create', 'update', 'delete'.")
    calendar_id: str = Field(default="primary", description="The ID of the calendar to interact with.")
    event_id: Optional[str] = Field(None, description="The ID of the event to update or delete.")
    start_time: Optional[str] = Field(None, description="The start time for a new event in ISO format (e.g., '2024-07-26T10:00:00').")
    end_time: Optional[str] = Field(None, description="The end time for a new event in ISO format (e.g., '2024-07-26T11:00:00').")
    summary: Optional[str] = Field(None, description="The summary or title of the event.")
    description: Optional[str] = Field(None, description="The description of the event.")
    attendees: Optional[List[str]] = Field(None, description="A list of attendee email addresses.")
    max_results: int = Field(10, description="The maximum number of events to return for the 'list' action.")


class GoogleCalendarTool(BaseTool):
    name: str = "google_calendar_tool"
    description: str = "A tool to interact with the Google Calendar API to manage calendar events."
    input_model = GoogleCalendarToolInput
    example_queries = [
        "구글 캘린더 일정 추가해줘", "일정 만들어줘",
        "오늘 스케줄 확인해줘", "미팅 등록해줘",
        "일정 삭제해줘", "calendar event 생성",
        "add event to calendar", "show my schedule",
    ]

    def _get_credentials(self) -> Credentials:
        """Gets valid user credentials from storage or initiates the OAuth2 flow."""
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except RefreshError as e:
                    # Handle the case where the refresh token is expired or revoked
                    print(f"Error refreshing token: {e}")
                    os.remove("token.json") # Remove the invalid token
                    return self._initiate_oauth_flow()
            else:
                return self._initiate_oauth_flow()
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        return creds
        
    def _initiate_oauth_flow(self) -> Credentials:
        """Initiates the OAuth2 flow to get new credentials."""
        flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        return creds


    async def execute(self, args: GoogleCalendarToolInput, context: ToolExecutionContext) -> ToolResult:
        """Executes the specified Google Calendar action."""
        try:
            creds = self._get_credentials()
            service = build("calendar", "v3", credentials=creds)

            if args.action == "list":
                return self._list_events(service, args)
            elif args.action == "create":
                return self._create_event(service, args)
            elif args.action == "update":
                return self._update_event(service, args)
            elif args.action == "delete":
                return self._delete_event(service, args)
            else:
                return ToolResult.error(f"Invalid action: {args.action}. Must be one of 'list', 'create', 'update', 'delete'.")

        except FileNotFoundError:
            return ToolResult.error(
                "Error: 'credentials.json' not found. "
                "Please obtain your OAuth 2.0 Client IDs from the Google Cloud Console "
                "and save them as 'credentials.json' in the same directory."
            )
        except HttpError as error:
            return ToolResult.error(f"An API error occurred: {error}")
        except Exception as e:
            return ToolResult.error(f"An unexpected error occurred: {e}")

    def _list_events(self, service, args: GoogleCalendarToolInput) -> ToolResult:
        """Lists the next upcoming events."""
        now = dt.datetime.utcnow().isoformat() + "Z"  # 'Z' indicates UTC time
        events_result = (
            service.events()
            .list(
                calendarId=args.calendar_id,
                timeMin=now,
                maxResults=args.max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])
        if not events:
            return ToolResult.success("No upcoming events found.")

        result_list = []
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            result_list.append(f"{start} - {event['summary']} (ID: {event['id']})")
        
        return ToolResult.success("\n".join(result_list))

    def _create_event(self, service, args: GoogleCalendarToolInput) -> ToolResult:
        """Creates a new event."""
        if not args.start_time or not args.end_time or not args.summary:
            return ToolResult.error("Missing required arguments for creating an event: start_time, end_time, summary.")

        event = {
            "summary": args.summary,
            "description": args.description,
            "start": {
                "dateTime": args.start_time,
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": args.end_time,
                "timeZone": "UTC",
            },
        }
        if args.attendees:
            event["attendees"] = [{"email": email} for email in args.attendees]

        created_event = service.events().insert(calendarId=args.calendar_id, body=event).execute()
        return ToolResult.success(f"Event created successfully. Event Link: {created_event.get('htmlLink')}")

    def _update_event(self, service, args: GoogleCalendarToolInput) -> ToolResult:
        """Updates an existing event."""
        if not args.event_id:
            return ToolResult.error("Missing required argument for updating an event: event_id.")

        # First, get the existing event
        try:
            event = service.events().get(calendarId=args.calendar_id, eventId=args.event_id).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return ToolResult.error(f"Event with ID '{args.event_id}' not found.")
            else:
                raise e

        # Update fields if new values are provided
        if args.summary:
            event["summary"] = args.summary
        if args.description:
            event["description"] = args.description
        if args.start_time:
            event["start"]["dateTime"] = args.start_time
        if args.end_time:
            event["end"]["dateTime"] = args.end_time
        if args.attendees:
            event["attendees"] = [{"email": email} for email in args.attendees]
        
        updated_event = service.events().update(calendarId=args.calendar_id, eventId=args.event_id, body=event).execute()
        return ToolResult.success(f"Event updated successfully. Event Link: {updated_event.get('htmlLink')}")

    def _delete_event(self, service, args: GoogleCalendarToolInput) -> ToolResult:
        """Deletes an event."""
        if not args.event_id:
            return ToolResult.error("Missing required argument for deleting an event: event_id.")
        
        try:
            service.events().delete(calendarId=args.calendar_id, eventId=args.event_id).execute()
            return ToolResult.success(f"Event with ID '{args.event_id}' deleted successfully.")
        except HttpError as e:
            if e.resp.status == 404:
                 return ToolResult.error(f"Event with ID '{args.event_id}' not found.")
            elif e.resp.status == 410: # Gone - indicates the event was already deleted
                 return ToolResult.success(f"Event with ID '{args.event_id}' was already deleted.")
            else:
                raise e
