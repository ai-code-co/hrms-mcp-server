from .utils import hrms_api_call


async def get_monthly_attendance(
    month: int,
    year: int,
    search: str = None,
    ordering: str = None,
    page: int = 1,
    userid: int = None
) -> str:
    """
    Get monthly attendance summary for an employee.
    :param month: Month number (1-12).
    :param year: Year (e.g., 2026).
    :param search: Optional search term.
    :param ordering: Optional ordering field.
    :param page: Page number for pagination.
    :param userid: Optional employee ID (admin only).
    """
    if month < 1 or month > 12:
        return "Error: 'month' must be between 1 and 12."

    params = {
        "month": month,
        "year": year,
        "page": page
    }
    if search:
        params["search"] = search
    if ordering:
        params["ordering"] = ordering
    if userid is not None:
        params["userid"] = userid

    return await hrms_api_call("/api/attendance/monthly/", "GET", params=params)
