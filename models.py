from sqlalchemy import Column, Integer, String
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # Должность в клане: chief / officer / sergeant / fighter.
    role = Column(String(20), nullable=False, default="fighter")
    # Специальный аккаунт с полным управлением должностями и будущими правами.
    is_superadmin = Column(Integer, nullable=False, default=0)
    # Игрок входит в текущий активный состав клана.
    active_roster = Column(Integer, nullable=False, default=0)

    # Игровой профиль. Все три характеристики вводятся игроком вручную.
    class_key = Column(String(30), nullable=True, default="vanguard_fighter")
    game_nickname = Column(String(50), nullable=True)
    attack = Column(Integer, nullable=True, default=0)
    defense = Column(Integer, nullable=True, default=0)
    accuracy = Column(Integer, nullable=True, default=0)

    # Выбранная карточка персонажа и изображения экипировки.
    character_card = Column(String(255), nullable=True)

    # Левая колонка
    weapon = Column(String(255), nullable=True)
    gloves = Column(String(255), nullable=True)
    cloak = Column(String(255), nullable=True)

    # Центральная колонка
    earring_1 = Column(String(255), nullable=True)
    earring_2 = Column(String(255), nullable=True)
    necklace = Column(String(255), nullable=True)
    belt = Column(String(255), nullable=True)
    bracelet_1 = Column(String(255), nullable=True)
    bracelet_2 = Column(String(255), nullable=True)
    ring_1 = Column(String(255), nullable=True)
    ring_2 = Column(String(255), nullable=True)
    totem = Column(String(255), nullable=True)
    seal = Column(String(255), nullable=True)

    # Правая колонка
    hat = Column(String(255), nullable=True)
    body = Column(String(255), nullable=True)
    pants = Column(String(255), nullable=True)
    boots = Column(String(255), nullable=True)

    # Нижняя панель
    symbol = Column(String(255), nullable=True)
    artifact = Column(String(255), nullable=True)


class CatalogImage(Base):
    __tablename__ = "catalog_images"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    class_key = Column(String(30), nullable=True, index=True)
    tier = Column(String(10), nullable=True, index=True)
    filename = Column(String(255), nullable=False, unique=True)
    image_url = Column(String(500), nullable=False)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    event_date = Column(String(30), nullable=True)
    event_type = Column(String(40), nullable=False, default="evening_prime", index=True)


class EventSetting(Base):
    __tablename__ = "event_settings"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(40), nullable=False, unique=True, index=True)
    # self = любой активный игрок отмечает только себя; admin = только Admin.
    attendance_mode = Column(String(20), nullable=False, default="self")


class EventAttendance(Base):
    __tablename__ = "event_attendance"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="present")


class ValuableItem(Base):
    __tablename__ = "valuable_items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    issued_to_user_id = Column(Integer, nullable=True, index=True)
    issued_at = Column(String(30), nullable=True)


class ClanSetting(Base):
    __tablename__ = "clan_settings"

    id = Column(Integer, primary_key=True, index=True)
    active_roster_limit = Column(Integer, nullable=False, default=33)
