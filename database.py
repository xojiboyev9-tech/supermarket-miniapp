import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Float, Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Railway'dan olingan DATABASE_URL ni tekshirish va to'g'rilash
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./supermarket.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite va PostgreSQL uchun mos ulanish
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)  # Katta Telegram ID lar uchun BigInteger
    full_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    role = Column(String, default="user")  # user, admin, super_admin, courier
    assigned_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    image_url = Column(String, nullable=True)
    stock = Column(Integer, default=0)
    unit = Column(String, default="dona")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProductRequest(Base):
    __tablename__ = "product_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False)  # Telegram ID saqlansa BigInteger bo'lishi shart
    product_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, nullable=False)  # Telegram ID saqlansa BigInteger bo'lishi shart
    items = Column(Text, nullable=False)
    total_amount = Column(Float, nullable=False)
    delivery_address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    phone = Column(String, nullable=True)
    payment_method = Column(String, default="cash")
    status = Column(String, default="new")
    created_at = Column(DateTime, default=datetime.utcnow)


class StoreSettings(Base):
    __tablename__ = "store_settings"

    id = Column(Integer, primary_key=True, index=True)
    store_name = Column(String, default="Supermarket")
    delivery_fee = Column(Float, default=0.0)
    min_order_amount = Column(Float, default=0.0)
    is_open = Column(Boolean, default=True)
    support_username = Column(String, nullable=True)


def init_db():
    # PostgreSQL'da eski Integer ustunlarni avtomatik BIGINT ga o'tkazish (xatolik chiqmasligi uchun)
    if "postgresql" in DATABASE_URL:
        with engine.begin() as conn:
            conn.execute(text("""
                DO $$ 
                BEGIN 
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='telegram_id') THEN
                        ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT;
                    END IF;
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='user_id') THEN
                        ALTER TABLE orders ALTER COLUMN user_id TYPE BIGINT;
                    END IF;
                    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='product_requests' AND column_name='user_id') THEN
                        ALTER TABLE product_requests ALTER COLUMN user_id TYPE BIGINT;
                    END IF;
                END $$;
            """))
    Base.metadata.create_all(bind=engine)
  
