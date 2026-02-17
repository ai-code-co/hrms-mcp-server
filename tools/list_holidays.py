from .utils import hrms_api_call

async def list_holidays(
    year: int = None,
    page: int = 1
) -> str:
    """
    Get the list of company holidays.
    :param year: Optional filter to see holidays for a specific year.
    :param page: Page number for pagination.
    """
    params = {"page": page}
    if year is not None:
        params["year"] = year
    return await hrms_api_call("/api/holidays/", "GET", params=params)