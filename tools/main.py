# tools/main.py
from .list_holidays import list_holidays
from .list_attendance import list_attendance
from .get_monthly_attendance import get_monthly_attendance
from .get_my_attendance_history import get_my_attendance_history
from .get_today_attendance import get_today_attendance
from .get_user_salary_info import get_user_salary_info
from .get_connection_link import get_connection_link
from .link_account_with_code import link_account_with_code 
from .create_attendance import create_attendance

ALL_TOOLS = [
    get_connection_link,
    link_account_with_code,
    list_holidays,
    list_attendance,
    get_monthly_attendance,
    get_my_attendance_history,
    get_today_attendance,
    get_user_salary_info,
    create_attendance,
]

def register_tools(mcp):
    for tool_fn in ALL_TOOLS:
        mcp.tool()(tool_fn)
