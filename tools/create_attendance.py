from .utils import hrms_api_call


async def create_attendance(
    employee: int,
    date: str,
    in_time: str = None,
    out_time: str = None,
    office_in_time: str = None,
    office_out_time: str = None,
    home_in_time: str = None,
    home_out_time: str = None,
    office_working_hours: str = None,
    orignal_total_time: int = None,
    day_type: str = None,
    day_text: str = None,
    text: str = None,
    is_working_from_home: bool = None,
) -> str:
    """
    Create attendance record (Admin only).
    Required: employee, date (YYYY-MM-DD)
    Date-time fields should be ISO format, e.g. 2026-02-17T09:30:00Z
    """
    payload = {
        "employee": employee,
        "date": date,
        "in_time": in_time,
        "out_time": out_time,
        "office_in_time": office_in_time,
        "office_out_time": office_out_time,
        "home_in_time": home_in_time,
        "home_out_time": home_out_time,
        "office_working_hours": office_working_hours,
        "orignal_total_time": orignal_total_time,
        "day_type": day_type,
        "day_text": day_text,
        "text": text,
        "is_working_from_home": is_working_from_home,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    return await hrms_api_call("/api/attendance/", "POST", json_data=payload)
