"""The tools of the MCP server.

They are plain functions, so they can be tested without an MCP client. `server.py`
registers them on the FastMCP server, wrapped so that they run one at a time (`vault.serialized`) :
their docstrings and type hints become the descriptions and the input schemas that the model reads.
"""

from teach_me.tools.courses import create_course, edit_course, get_course_state, list_courses
from teach_me.tools.deliverables import checkin_deliverable, correct_deliverable, create_deliverable, read_deliverable
from teach_me.tools.exams import correct_exam, create_exam, grade_questions, read_exam, submit_answers
from teach_me.tools.project import create_project, list_projects, update_project
from teach_me.tools.repair import migrate_vault, repair_note
from teach_me.tools.report import report_card
from teach_me.tools.resources import share_resource, update_resource
from teach_me.tools.sessions import log_session, save_class, start_session, update_class
from teach_me.tools.skill import create_skills, edit_skill, list_skills
from teach_me.tools.users import create_user, edit_user, get_user, list_users

ALL_TOOLS = [
    start_session,
    list_users,
    create_user,
    edit_user,
    get_user,
    list_projects,
    create_project,
    update_project,
    create_skills,
    list_skills,
    edit_skill,
    create_course,
    edit_course,
    list_courses,
    get_course_state,
    log_session,
    save_class,
    update_class,
    create_exam,
    submit_answers,
    read_exam,
    grade_questions,
    correct_exam,
    create_deliverable,
    read_deliverable,
    checkin_deliverable,
    correct_deliverable,
    share_resource,
    update_resource,
    report_card,
    repair_note,
    migrate_vault,
]
