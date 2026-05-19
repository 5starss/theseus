from fastapi import APIRouter, HTTPException, status
from src.tooling.service import move_tool_to_trash

router = APIRouter()

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
