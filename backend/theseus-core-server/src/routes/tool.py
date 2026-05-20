from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from src.tooling.service import move_tool_to_trash, update_tool_permission_level

router = APIRouter()


class ToolPermissionLevelUpdateRequest(BaseModel):
    permissionLevel: int = Field(ge=1, le=5)

@router.delete("/tools/{project_id}/{tool_name}")
async def delete_tool_endpoint(project_id: str, tool_name: str):
    try:
        moved = move_tool_to_trash(project_id, tool_name)
        if not moved:
            return {"status": "skipped", "message": "No physical files found to delete."}
        return {"status": "success", "message": f"Successfully moved tool {tool_name} to trash."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete tool: {str(e)}"
        )


@router.patch("/tools/{project_id}/{tool_name}/permission-level")
async def update_tool_permission_level_endpoint(
    project_id: str,
    tool_name: str,
    request: ToolPermissionLevelUpdateRequest,
):
    try:
        updated = update_tool_permission_level(project_id, tool_name, request.permissionLevel)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tool metadata file not found.",
            )
        return {
            "status": "success",
            "message": f"Successfully updated tool {tool_name} permissionLevel.",
            "permissionLevel": request.permissionLevel,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update tool permissionLevel: {str(e)}",
        )
