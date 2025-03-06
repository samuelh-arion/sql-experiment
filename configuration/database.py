from peewee import *
from datetime import datetime

database = SqliteDatabase("local.db")

database.autoconnect = True

"""
PEEWEE ORM DATACLASSES
"""


class BaseModel(Model):
    class Meta:
        database = database


class Employees(BaseModel):
    id = AutoField()
    updated_at = DateTimeField(null=False, default=datetime.now)
    full_name = CharField(null=False)
    nationality = CharField(null=False)
    department = CharField(null=False)
    is_manager = BooleanField(null=False)
    location = CharField(null=False)
    linkedin = CharField(null=False)
    twitter_x = CharField(null=False)
    facebook = CharField(null=False)
    email = CharField(null=False, unique=True)
    is_active = BooleanField(null=False, default=True)
    reports_to = ForeignKeyField("self", null=False, backref="direct_reports")
    birth_date = DateField(null=False)
    client = CharField(null=False)

    class Meta:
        table_name = "employees"


class TimeOff(BaseModel):
    id = AutoField()
    employee = ForeignKeyField(Employees, backref="time_offs")
    policy_type = CharField()
    start_date = DateField()
    end_date = DateField()
    type = CharField()  # vacation, birthday, holiday
    status = CharField(default="pending")  # pending, approved, rejected
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        table_name = "time_off"
        indexes = (
            (("employee", "start_date", "end_date"), False),  # False means not unique
        )


def create_tables():
    with database:
        database.create_tables([Employees, TimeOff])


def reset_database():
    """
    Drops all tables and recreates them with synthetic data using Faker
    """
    from data_generation.generate_data import (
        generate_employee_data,
        generate_time_off_data,
    )

    with database:
        database.drop_tables([Employees, TimeOff])
        database.create_tables([Employees, TimeOff])

        # Generate synthetic data
        generate_employee_data()
        generate_time_off_data()


# Only create tables if they don't exist
if not Employees.table_exists() or not TimeOff.table_exists():
    reset_database()
