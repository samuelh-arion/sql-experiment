from faker import Faker
from datetime import datetime, timedelta
import random
import sys
import os
import concurrent.futures

# Add the parent directory to the Python path so we can import the database module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from configuration.database import Employees, TimeOff, database

fake = Faker()

# Set random seed for reproducibility
Faker.seed(12345)
random.seed(12345)


def generate_employee_data(num_employees=50):
    """Generate synthetic employee data"""
    # Create CEO first (reports to self)
    ceo = Employees.create(
        full_name=fake.name(),
        nationality=fake.country(),
        department="Executive",
        is_manager=True,
        location=fake.city(),
        linkedin=f"linkedin.com/in/{fake.user_name()}",
        twitter_x=f"twitter.com/{fake.user_name()}",
        facebook=f"facebook.com/{fake.user_name()}",
        email=fake.company_email(),
        is_active=True,
        reports_to=1,  # Will be set to self after creation
        birth_date=fake.date_of_birth(minimum_age=30, maximum_age=65),
        client="Internal",
    )

    # Update CEO to report to self
    ceo.reports_to = ceo
    ceo.save()

    # Department structure
    departments = {
        "Engineering": {
            "weight": 0.4,
            "locations": ["San Francisco", "Bangalore", "London"],
        },
        "Marketing": {"weight": 0.2, "locations": ["New York", "London", "Singapore"]},
        "Sales": {"weight": 0.2, "locations": ["Chicago", "Paris", "Sydney"]},
        "HR": {"weight": 0.1, "locations": ["Toronto", "Berlin", "Tokyo"]},
        "Finance": {"weight": 0.1, "locations": ["London", "Hong Kong", "New York"]},
    }

    # Create department heads (managers)
    managers = {dept: [] for dept in departments}
    for dept in departments:
        num_managers = random.randint(1, 3)
        for _ in range(num_managers):
            manager = Employees.create(
                full_name=fake.name(),
                nationality=fake.country(),
                department=dept,
                is_manager=True,
                location=random.choice(departments[dept]["locations"]),
                linkedin=f"linkedin.com/in/{fake.user_name()}",
                twitter_x=f"twitter.com/{fake.user_name()}",
                facebook=f"facebook.com/{fake.user_name()}",
                email=fake.company_email(),
                is_active=True,
                reports_to=ceo,
                birth_date=fake.date_of_birth(minimum_age=30, maximum_age=55),
                client="Internal",
            )
            managers[dept].append(manager)

    # Create regular employees in parallel
    remaining_employees = num_employees - sum(len(m) for m in managers.values()) - 1

    def create_employee(_):
        # Select department based on weights
        dept = random.choices(
            list(departments.keys()),
            weights=[d["weight"] for d in departments.values()],
        )[0]

        # Select random manager from department
        manager = random.choice(managers[dept])

        Employees.create(
            full_name=fake.name(),
            nationality=fake.country(),
            department=dept,
            is_manager=False,
            location=random.choice(departments[dept]["locations"]),
            linkedin=f"linkedin.com/in/{fake.user_name()}",
            twitter_x=f"twitter.com/{fake.user_name()}",
            facebook=f"facebook.com/{fake.user_name()}",
            email=fake.company_email(),
            is_active=random.random() > 0.05,  # 5% chance of inactive
            reports_to=manager,
            birth_date=fake.date_of_birth(minimum_age=22, maximum_age=65),
            client=random.choice(["Internal", "ProjectX", "ProjectY", "ProjectZ"]),
        )

    # Use ThreadPoolExecutor for parallel employee creation
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(create_employee, range(remaining_employees)))


def create_time_off_for_employee(employee):
    """Create time off requests for a single employee"""
    policy_types = [
        ("PTO", "Paid Time Off"),
        ("SICK", "Sick Leave"),
        ("HOLIDAY", "Public Holiday"),
        ("BIRTHDAY", "Birthday Leave"),
        ("PARENTAL", "Parental Leave"),
    ]

    statuses = ["approved", "pending", "rejected"]
    status_weights = [0.7, 0.2, 0.1]  # 70% approved, 20% pending, 10% rejected

    num_requests = random.randint(1, 5)
    requests = []

    for _ in range(num_requests):
        policy_type, display_name = random.choice(policy_types)

        # Generate random dates within next year
        start_date = fake.date_between(
            start_date=datetime.now(), end_date=datetime.now() + timedelta(days=365)
        )

        # Duration based on type
        if policy_type in ["HOLIDAY", "BIRTHDAY"]:
            duration = 1
        elif policy_type == "PARENTAL":
            duration = random.randint(30, 90)
        else:
            duration = random.randint(1, 14)

        end_date = start_date + timedelta(days=duration - 1)

        requests.append(
            {
                "employee": employee,
                "policy_type": policy_type,
                "start_date": start_date,
                "end_date": end_date,
                "type": "vacation" if policy_type == "PTO" else policy_type.lower(),
                "status": random.choices(statuses, weights=status_weights)[0],
                "created_at": fake.date_time_between(start_date="-30d", end_date="now"),
                "updated_at": datetime.now(),
            }
        )

    return requests


def generate_time_off_data():
    """Generate synthetic time off data for each employee in parallel"""
    employees = list(Employees.select())

    # Create time off requests for each employee in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        all_requests = list(executor.map(create_time_off_for_employee, employees))

    # Flatten the list of requests
    flattened_requests = [request for sublist in all_requests for request in sublist]

    # Bulk create the time off requests
    with database.atomic():
        for i in range(0, len(flattened_requests), 100):  # Process in batches of 100
            batch = flattened_requests[i : i + 100]
            TimeOff.insert_many(batch).execute()


def main():
    print("Starting data generation...")
    start_time = datetime.now()

    # Reset database
    with database:
        database.drop_tables([Employees, TimeOff])
        database.create_tables([Employees, TimeOff])

    # Generate data
    print("Generating employee data...")
    generate_employee_data()

    print("Generating time off data...")
    generate_time_off_data()

    end_time = datetime.now()
    print(f"Data generation completed in {end_time - start_time}")


if __name__ == "__main__":
    main()
