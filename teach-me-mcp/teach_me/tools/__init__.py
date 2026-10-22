"""The tools of the MCP server.

They are plain functions, so they can be tested without an MCP client. `server.py`
registers them on the FastMCP server : their docstrings and type hints become the
descriptions and the input schemas that the model reads.
"""

from teach_me.tools.courses import create_course, create_project, get_course_state, list_courses
from teach_me.tools.exams import correct_exam, create_exam, read_exam
from teach_me.tools.report import report_card
from teach_me.tools.resources import share_resource, update_resource
from teach_me.tools.sessions import log_session, save_class
from teach_me.tools.users import create_user, edit_user, get_user, list_users

ALL_TOOLS = [
    list_users,
    create_user,
    edit_user,
    get_user,
    create_project,
    create_course,
    list_courses,
    get_course_state,
    log_session,
    save_class,
    create_exam,
    read_exam,
    correct_exam,
    share_resource,
    update_resource,
    report_card,
]
