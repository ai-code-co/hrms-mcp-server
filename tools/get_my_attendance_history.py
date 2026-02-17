from .utils import hrms_api_call

async def get_my_attendance_history(
    start_date: str = None,
    end_date: str = None,
    search: str = None,
    ordering: str = None,
    page: int = 1
) -> str:
    """
    Get logged-in employee attendance history.
    :param start_date: Optional start date (YYYY-MM-DD).
    :param end_date: Optional end date (YYYY-MM-DD).
    :param search: Optional search term.
    :param ordering: Optional ordering field.
    :param page: Page number for pagination.
    """
    params = {"page": page}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if search:
        params["search"] = search
    if ordering:
        params["ordering"] = ordering

    return await hrms_api_call("/api/attendance/my-attendance/","GET", params=params)