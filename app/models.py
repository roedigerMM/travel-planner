# app/models.py
import enum
from datetime import UTC, datetime

from .extensions import db


class TripType(enum.Enum):
    CITY_TRIP = "CITY_TRIP"
    NATURE_HIKING = "NATURE_HIKING"
    WATER_SPORTS = "WATER_SPORTS"
    SPA_RELAX = "SPA_RELAX"
    BACKPACKING = "BACKPACKING"


class OriginSubType(enum.Enum):
    AIRPORT = "AIRPORT"
    CITY = "CITY"


class SearchOriginStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    NO_RESULTS = "NO_RESULTS"
    ERROR = "ERROR"


class Search(db.Model):
    __tablename__ = "search"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    # Stored as "YYYY-MM"
    travel_month = db.Column(db.String(7), nullable=True)

    duration_days = db.Column(db.Integer, nullable=True)

    max_price = db.Column(db.Numeric(10, 2), nullable=True)
    currency_code = db.Column(db.String(3), nullable=True)

    non_stop = db.Column(db.Boolean, nullable=True)

    trip_type = db.Column(
        db.Enum(TripType, name="trip_type", create_constraint=True),
        nullable=True,
    )
    preference_summary = db.Column(db.Text, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="PENDING")
    error_message = db.Column(db.Text, nullable=True)

    origins = db.relationship(
        "SearchOrigin",
        back_populates="search",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    candidates = db.relationship(
        "DestinationCandidate",
        back_populates="search",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    preferences = db.relationship(
        "SearchPreference",
        back_populates="search",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SearchPreference.position",
    )

    def to_dict(self, include_children=False):
        data = {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "travel_month": self.travel_month,
            "duration_days": self.duration_days,
            "max_price": float(self.max_price) if self.max_price is not None else None,
            "currency_code": self.currency_code,
            "non_stop": self.non_stop,
            "trip_type": self.trip_type.value if self.trip_type else None,
            "preference_summary": self.preference_summary,
            "status": self.status,
            "error_message": self.error_message,
        }
        if include_children:
            data["origins"] = [o.to_dict() for o in self.origins]
            data["candidates"] = [c.to_dict() for c in self.candidates]
            data["preferences"] = [p.to_dict() for p in self.preferences]
        return data


class SearchPreference(db.Model):
    __tablename__ = "search_preference"

    id = db.Column(db.Integer, primary_key=True)
    search_id = db.Column(
        db.Integer,
        db.ForeignKey("search.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(80), nullable=False)
    source = db.Column(db.String(20), nullable=False, default="USER")
    position = db.Column(db.Integer, nullable=False, default=0)

    search = db.relationship("Search", back_populates="preferences")

    def to_dict(self):
        return {
            "id": self.id,
            "search_id": self.search_id,
            "label": self.label,
            "source": self.source,
            "position": self.position,
        }


class SearchOrigin(db.Model):
    __tablename__ = "search_origin"

    id = db.Column(db.Integer, primary_key=True)

    search_id = db.Column(
        db.Integer,
        db.ForeignKey("search.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    iata_code = db.Column(db.String(3), nullable=False)
    provider_sky_id = db.Column(db.String(20), nullable=True)
    provider_entity_id = db.Column(db.String(40), nullable=True)

    sub_type = db.Column(
        db.Enum(OriginSubType, name="origin_sub_type", create_constraint=True),
        nullable=False,
    )
    status = db.Column(
        db.Enum(SearchOriginStatus, name="search_origin_status", create_constraint=True),
        nullable=False,
        default=SearchOriginStatus.PENDING,
    )
    error_message = db.Column(db.Text, nullable=True)

    search = db.relationship("Search", back_populates="origins")

    def to_dict(self):
        return {
            "id": self.id,
            "search_id": self.search_id,
            "iata_code": self.iata_code,
            "provider_sky_id": self.provider_sky_id,
            "provider_entity_id": self.provider_entity_id,
            "sub_type": self.sub_type.value,
            "status": self.status.value if self.status else None,
            "error_message": self.error_message,
        }


class DestinationCandidate(db.Model):
    __tablename__ = "destination_candidate"

    id = db.Column(db.Integer, primary_key=True)

    search_id = db.Column(
        db.Integer,
        db.ForeignKey("search.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    origin_iata = db.Column(db.String(3), nullable=False)
    destination_code = db.Column(db.String(20), nullable=False)
    destination_iata = db.Column(db.String(3), nullable=True)
    destination_entity_id = db.Column(db.String(40), nullable=True)
    destination_name = db.Column(db.String(120), nullable=True)
    destination_type = db.Column(db.String(20), nullable=True)

    price = db.Column(db.Numeric(10, 2), nullable=True)
    currency_code = db.Column(db.String(3), nullable=True)
    departure_date = db.Column(db.String(10), nullable=True)

    ai_fit_score = db.Column(db.Integer, nullable=True)
    ai_rationale = db.Column(db.Text, nullable=True)

    raw_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(UTC))

    search = db.relationship("Search", back_populates="candidates")

    __table_args__ = (
        db.UniqueConstraint(
            "search_id", "origin_iata", "destination_code",
            name="uq_candidate_search_origin_dest_code",
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "search_id": self.search_id,
            "origin_iata": self.origin_iata,
            "destination_code": self.destination_code,
            "destination_iata": self.destination_iata,
            "destination_entity_id": self.destination_entity_id,
            "destination_name": self.destination_name,
            "destination_type": self.destination_type,
            "price": float(self.price) if self.price is not None else None,
            "currency_code": self.currency_code,
            "departure_date": self.departure_date,
            "ai_fit_score": self.ai_fit_score,
            "ai_rationale": self.ai_rationale,
        }
