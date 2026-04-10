from app.models.user import User
from app.models.course import Course, CompletedCourse
from app.models.requirement import DegreeRequirement, RequirementType
from app.models.professor import Professor
from app.models.review import Review
from app.models.section import Section
from app.models.cart import CartItem
from app.models.wishlist import WishlistItem

__all__ = [
    "User",
    "Course",
    "CompletedCourse",
    "DegreeRequirement",
    "RequirementType",
    "Professor",
    "Review",
    "Section",
    "CartItem",
    "WishlistItem",
]
