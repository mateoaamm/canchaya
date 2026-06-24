"""Enumeraciones del dominio. Centralizadas para reusarlas en modelos y schemas."""

from enum import Enum


class UserRole(str, Enum):
    CLIENT = "client"
    STAFF = "staff"
    ADMIN = "admin"


class BookingStatus(str, Enum):
    PENDING = "pending"  # creada, esperando confirmacion de pago
    CONFIRMED = "confirmed"  # pago confirmado por staff
    CANCELLED = "cancelled"  # cancelada por cliente/staff/admin


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    REFUNDED = "refunded"


class Surface(str, Enum):
    SYNTHETIC = "synthetic"
    GRASS = "grass"
    INDOOR = "indoor"
