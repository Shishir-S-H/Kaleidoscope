import uuid

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Boolean,
    Integer,
    Float,
    ForeignKey,
    ARRAY,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector


Base = declarative_base()


class Image(Base):
    __tablename__ = "images"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    s3_key = Column(String, nullable=False, index=True)
    uploader_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    status = Column(String, nullable=False, default="uploaded", index=True)
    is_safe = Column(Boolean, nullable=True)
    caption = Column(String, nullable=True)
    tags = Column(ARRAY(String), nullable=True)
    scenes = Column(ARRAY(String), nullable=True)
    embedding = Column(Vector(512), nullable=True)

    # Relationships
    faces = relationship(
        "DetectedFace",
        back_populates="image",
        cascade="all, delete-orphan",
    )


class DetectedFace(Base):
    __tablename__ = "detected_faces"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    image_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("images.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id = Column(String, nullable=True, index=True)
    bbox = Column(ARRAY(Integer), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    emotion = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

    # Relationships
    image = relationship("Image", back_populates="faces")


