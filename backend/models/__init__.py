"""ORM models. Importing this package registers every table on Base.metadata."""

from models.clinical import Appointment, Doctor, EmergencyCase, Patient
from models.recommendation import Recommendation
from models.resources import Bed, Equipment, Staff
from models.system_state import SystemState
from models.user import User

__all__ = ["Appointment", "Bed", "Doctor", "EmergencyCase", "Equipment", "Patient", "Recommendation",
           "Staff", "SystemState", "User"]
