from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    BigInteger,
    String,
    DateTime,
    Date,
    ForeignKey,
    Text,
    Index,
    func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    school: Mapped[str] = mapped_column(String(150), nullable=False)
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    admin_histories: Mapped[list["AdminHistory"]] = relationship("AdminHistory", back_populates="user", cascade="all, delete-orphan")
    messages: Mapped[list["SchoolMessage"]] = relationship("SchoolMessage", back_populates="sender", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_user_school_grade", "school", "grade"),
    )


class AdminHistory(Base):
    __tablename__ = "admin_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assignment_date: Mapped[date] = mapped_column(Date, nullable=False)
    school: Mapped[str] = mapped_column(String(150), nullable=False)
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="admin_histories")

    __table_args__ = (
        Index("idx_admin_school_grade_date", "school", "grade", "assignment_date"),
    )


class SchoolMessage(Base):
    __tablename__ = "school_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    school: Mapped[str] = mapped_column(String(150), nullable=False)
    grade: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False) # homework, schedule, announcement, etc.
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    photo_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sender: Mapped["User"] = relationship("User", back_populates="messages")

    __table_args__ = (
        Index("idx_msg_school_grade", "school", "grade"),
    )
