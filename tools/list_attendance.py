from .utils import hrms_api_call

async def list_attendance(
    search: str = None,
    ordering: str = None,
    page: int = 1
) -> str:
    """
    Get attendance records.
    :param search: Optional search term.
    :param ordering: Optional ordering field.
    :param page: Page number for pagination.
    """
    params = {"page": page}
    if search:
        params["search"] = search
    if ordering:
        params["ordering"] = ordering
    return await hrms_api_call("/api/attendance/","GET", params=params)