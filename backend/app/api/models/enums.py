from enum import Enum


class BusinessCategory(str, Enum):
    RESTAURANT = "restaurant"


class ServiceMode(str, Enum):
    DINE_IN = "dineIn"
    TAKEOUT = "takeout"
    DELIVERY = "delivery"
    RESERVATION = "reservation"


class GenerationStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
