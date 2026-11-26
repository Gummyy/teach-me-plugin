import pytest

from teach_me.database.vault import VAULT_ENV
from teach_me.tools import create_course, create_project, create_skills, create_user

ONE_STEP = [{"kind": "class", "title": "First class", "description": "", "skills": [], "importance": "core"}]
"""The smallest plan, for the courses whose plan doesn't matter to the test."""
PLAN = [
    {"kind": "class", "title": "Convolution", "description": "Kernels and feature maps", "skills": ["convolution"], "importance": "core"},
    {"kind": "quiz", "title": "Convolution quiz", "description": "", "skills": ["convolution"], "importance": "core"},
    {"kind": "class", "title": "CNN architectures", "description": "", "skills": ["cnn-architecture"], "importance": "core"},
    {"kind": "deliverable", "title": "First CNN", "description": "Train a CNN on the pictures", "skills": ["convolution", "cnn-architecture"], "importance": "core"},
]
"""The plan of the computer-vision course."""


@pytest.fixture
def vault(tmp_path, monkeypatch):
    """An empty vault in a temporary folder."""
    monkeypatch.setenv(VAULT_ENV, str(tmp_path))
    return tmp_path


@pytest.fixture
def course(vault):
    """A vault with one user (alice), one project (pet-classifier), two skills (convolution, cnn-architecture) and one course (computer-vision), planned with PLAN."""
    create_user("Alice", {"language": "french"}, "Likes photography")
    create_project("alice", "Pet classifier", "Classify the pictures of my cats and dogs.")
    skills = create_skills(
        "alice",
        [
            {"name": "convolution", "description": "Computes and interprets a 2D convolution"},
            {"name": "cnn-architecture", "description": "Designs a small CNN for image classification"},
        ],
    )
    return create_course(
        "alice",
        subject="Computer vision with convolutional neural networks.",
        starting_level="Knows linear algebra and basic neural networks.",
        skills=[skill["slug"] for skill in skills],
        plan=PLAN,
        projects=["pet-classifier"],
        name="Computer vision",
    )["slug"]
