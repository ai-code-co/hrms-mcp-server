from .utils import hrms_api_call

async def get_user_salary_info(
    userid: int = None,
    month: int = None,
    year: int = None
) -> str:
    """
    Get salary info from user-salary-info endpoint.
    The backend enforces role-based visibility and access rules.
    :param userid: Optional employee ID.
    :param month: Optional month (1-12).
    :param year: Optional year (e.g., 2026).
    """
    if month is not None and (month < 1 or month > 12):
        return "Error: 'month' must be between 1 and 12."

    params = {}
    if userid is not None:
        params["userid"] = userid
    if month is not None:
        params["month"] = month
    if year is not None:
        params["year"] = year

    return await hrms_api_call( "/api/payroll/user-salary-info/","GET", params=params or None)