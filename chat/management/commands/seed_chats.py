from django.core.management.base import BaseCommand
from core.models import User  # Use User from core.models
from chat.models import Conversation, ConversationParticipant, Message

class Command(BaseCommand):
    help = 'Seed sample conversations and messages for chat testing (clients and freelancers)'

    def handle(self, *args, **kwargs):
        # Pick any 2 clients and 2 freelancers
        clients = list(User.objects.filter(role='client').order_by('id')[:2])
        freelancers = list(User.objects.filter(role='freelancer').order_by('id')[:2])
        
        if len(clients) < 2 or len(freelancers) < 2:
            self.stdout.write(self.style.ERROR("Not enough clients or freelancers in the database."))
            return

        client1, client2 = clients
        freelancer1, freelancer2 = freelancers

        # Define the 4 conversation pairs
        convo_users = [
            (client1, client2),         # client1-client2
            (freelancer1, freelancer2), # freelancer1-freelancer2
            (freelancer1, client1),     # freelancer1-client1
            (freelancer2, client2),     # freelancer2-client2
        ]

        for user1, user2 in convo_users:
            # Check if a 1-to-1 conversation between these users exists (order-independent)
            existing_convos = Conversation.objects.filter(
                is_group=False,
                participants__user=user1
            ).filter(
                participants__user=user2
            ).distinct()

            if existing_convos.exists():
                convo = existing_convos.first()
                self.stdout.write(self.style.WARNING(
                    f"Conversation already exists for users {user1.id}, {user2.id} (id={convo.id})"
                ))
            else:
                convo = Conversation.objects.create(is_group=False)
                ConversationParticipant.objects.create(conversation=convo, user=user1)
                ConversationParticipant.objects.create(conversation=convo, user=user2)
                self.stdout.write(self.style.SUCCESS(
                    f"Created Conversation {convo.id} for users {user1.id} ({user1.username}), {user2.id} ({user2.username})"
                ))

            # Add sample messages (always, for demo purposes)
            Message.objects.create(conversation=convo, sender=user1, content=f"Hello from user {user1.id} to {user2.id}!")
            Message.objects.create(conversation=convo, sender=user2, content=f"Hi user {user1.id}, this is user {user2.id}!")
            Message.objects.create(conversation=convo, sender=user1, content="How are you?")
            Message.objects.create(conversation=convo, sender=user2, content="I'm good, thanks!")

        self.stdout.write(self.style.SUCCESS("Seeding complete!"))
