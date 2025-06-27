from django.core.management.base import BaseCommand
from core.models import Category, Skill, User
from Profile.models import ClientProfile, FreelancerProfile
from client.models import Activity


class Command(BaseCommand):
    help = "Manually insert data into the database from the all_data.json file"

    def handle(self, *args, **kwargs):
        # Inserting Categories
        categories_data = [
            {"name": "Content Writing", "description": "Writing"},
            {"name": "Copywriting", "description": "Copywriting"},
            {"name": "Technical Writing", "description": "Technical Writing"},
            {"name": "Graphic Design", "description": "Graphic Design"},
            {"name": "Web Design", "description": "Web Design"},
            {"name": "Web Development", "description": "Web Development"},
            {"name": "Mobile App Development", "description": "Mobile App Development"},
            {"name": "Digital Marketing", "description": "Digital Marketing"},
            {"name": "Social Media Management", "description": "Social Media Management"},
            {"name": "Virtual Assistance", "description": "Virtual Assistance"},
            {"name": "Translation", "description": "Skills related to Translation"},
            {"name": "Video Editing", "description": "Skills related to Video Editing"},
            {"name": "Data Science", "description": "Skills related to Data Science"},
            {"name": "Finance & Accounting", "description": "Skills related to Finance & Accounting"},
            {"name": "Project Management", "description": "Skills related to Project Management"},
            {"name": "E-commerce Management", "description": "Skills related to E-commerce Management"},
            {"name": "Customer Support", "description": "Skills related to Customer Support"},
            {"name": "Human Resources", "description": "Skills related to Human Resources"},
            {"name": "Legal", "description": "Skills related to Legal"},
            {"name": "Education & Training", "description": "Skills related to Education & Training"},
            {"name": "Music & Audio", "description": "Skills related to Music & Audio"},
            {"name": "3D Modeling & Animation", "description": "Skills related to 3D Modeling & Animation"},
            {"name": "Game Development", "description": "Skills related to Game Development"}
        ]

        for category in categories_data:
            Category.objects.get_or_create(name=category["name"], defaults={"description": category["description"]})

        # Inserting Skills (Sample for a few categories)
        skills_data = [
            {"category": "Content Writing", "name": "Blog Post Writing", "description": "Skill: Blog Post Writing"},
            {"category": "Content Writing", "name": "Article Writing", "description": "Skill: Article Writing"},
            {"category": "Content Writing", "name": "SEO Writing", "description": "Skill: SEO Writing"},
            {"category": "Copywriting", "name": "Sales Letter Writing", "description": "Skill: Sales Letter Writing"},
            {"category": "Copywriting", "name": "Ad Copywriting", "description": "Skill: Ad Copywriting"},
            {"category": "Web Development", "name": "HTML/CSS", "description": "Skill: HTML/CSS"},
            {"category": "Web Development", "name": "API Development", "description": "Skill: API Development"},
            {"category": "Mobile App Development", "name": "iOS Development", "description": "Skill: iOS Development"}
        ]

        for skill in skills_data:
            category_instance = Category.objects.get(name=skill["category"])
            Skill.objects.get_or_create(category=category_instance, name=skill["name"], defaults={"description": skill["description"]})

        # Inserting Users
        users_data = [
            {"username": "admin", "is_superuser": True, "is_staff": True, "email": "", "role": "freelancer", "membership": "free"},
            {"username": "Sadguru", "is_superuser": False, "is_staff": False, "email": "sadgurustreak@gmail.com", "role": "freelancer", "membership": "free"},
            {"username": "A", "is_superuser": False, "is_staff": False, "email": "pokaw@mailinator.com", "role": "client", "membership": "free"},
        ]

        for user in users_data:
            User.objects.get_or_create(username=user["username"], defaults={
                "is_superuser": user["is_superuser"],
                "is_staff": user["is_staff"],
                "email": user["email"],
                "role": user["role"],
                "membership": user["membership"]
            })

        # Insert other models in a similar manner
        # For example, for Tasks, Projects, etc.

        self.stdout.write(self.style.SUCCESS("Data inserted successfully!"))
