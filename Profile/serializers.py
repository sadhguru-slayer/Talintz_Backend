from rest_framework import serializers
from .models import ClientProfile,FreelancerProfile,Feedback, Address, CompanyDetails,BankDetails,VerificationDocument
from core.models import Connection
from django.contrib.auth import get_user_model
import json
from datetime import datetime
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

User = get_user_model()  # This will point to your custom User model if defined

class VerificationDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationDocument
        fields = '__all__'

    def update(self, instance, validated_data):
        verification_documents_data = self.initial_data.get('verification_documents', [])
        
        try:
            # Handle existing documents
            existing_docs = {doc.id: doc for doc in instance.verification_documents.all()}
            
            for doc_data in verification_documents_data:
                doc_id = doc_data.get('id')
                if doc_id and doc_id in existing_docs:
                    # Update existing document
                    doc = existing_docs[doc_id]
                    for field, value in doc_data.items():
                        setattr(doc, field, value)
                    doc.save()
                else:
                    # Create new document
                    VerificationDocument.objects.create(
                        client_profile=instance,
                        **{k: v for k, v in doc_data.items() if k != 'id'}
                    )
            
            # Delete documents that were removed
            kept_ids = [doc.get('id') for doc in verification_documents_data if doc.get('id')]
            instance.verification_documents.exclude(id__in=kept_ids).delete()
            
        except Exception as e:
            raise serializers.ValidationError(f"Error handling verification documents: {str(e)}")
        
        return super().update(instance, validated_data)


class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = '__all__'

class BankDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankDetails
        fields = '__all__'

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'
        extra_kwargs = {
            'street_address': {'required': True},
            'city': {'required': True},
            'state': {'required': True},
            'country': {'required': True},
            'postal_code': {'required': True},
            'address_type': {'required': False, 'default': 'registered'},
            'is_primary': {'required': False, 'default': False},
            'verified': {'required': False, 'default': False}
        }

class CompanyDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyDetails
        fields = '__all__'

class ClientProfilePartialUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.username', read_only=True)
    addresses = AddressSerializer(many=True, required=False)
    bank_details = BankDetailsSerializer(required=False)
    verification_documents = serializers.ListField(required=False, allow_empty=True)
    business_preferences = serializers.DictField(required=False, allow_empty=True)
    company = CompanyDetailsSerializer(required=False)

    class Meta:
        model = ClientProfile
        fields = [
            'name', 'bio', 'description', 'profile_picture', 'cover_photo', 'gender', 'dob',
            'primary_email', 'secondary_email', 'phone_number', 'alternate_phone',
            'addresses', 'bank_details', 'verification_documents', 'business_preferences',
            'email_verified', 'phone_verified', 'identity_verified', 'profile_status',
            'account_tier', 'terms_accepted', 'privacy_policy_accepted',
            'preferred_payment_method', 'budget_range', 'company'
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Include bank details in the response
        if instance.bank_details:
            ret['bank_details'] = {
                'id': instance.bank_details.id,
                'bank_name': instance.bank_details.bank_name,
                'account_number': instance.bank_details.account_number,
                'ifsc_code': instance.bank_details.ifsc_code,
                'account_holder_name': instance.bank_details.account_holder_name,
                'branch_name': instance.bank_details.branch_name,
                'swift_code': instance.bank_details.swift_code,
                'primary': instance.bank_details.primary
            }
        return ret

    def update(self, instance, validated_data):
        try:
            print("Starting optimized update method in serializer")
            
            # Extract nested data from initial_data (not validated_data)
            addresses_data = self.initial_data.get('addresses')
            bank_details_data = self.initial_data.get('bank_details')
            verification_docs_data = self.initial_data.get('verification_documents')
            company_data = self.initial_data.get('company')
            business_prefs_data = self.initial_data.get('business_preferences')
            
            # HANDLE ADDRESSES - only if present in request
            if addresses_data:
                self._handle_addresses(instance, addresses_data)
                
            # HANDLE BANK DETAILS - only if present in request
            if bank_details_data:
                self._handle_bank_details(instance, bank_details_data)

            # HANDLE COMPANY DETAILS - only if present in request
            if company_data:
                self._handle_company(instance, company_data)

            # HANDLE VERIFICATION DOCUMENTS - only if present in request
            if verification_docs_data:
                self._handle_verification_docs(instance, verification_docs_data)

            # HANDLE BUSINESS PREFERENCES - only if present in request
            if business_prefs_data:
                self._handle_business_preferences(instance, business_prefs_data, validated_data)

            # Update direct fields from validated_data if they exist and have changed
            self._update_direct_fields(instance, validated_data)

            instance.save()
            print("Profile updated successfully in serializer")
            return instance

        except Exception as e:
            print(f"Error in serializer update method: {str(e)}")
            raise serializers.ValidationError(f"Error updating profile: {str(e)}")

    def _update_direct_fields(self, instance, validated_data):
        """Only update direct fields if they have changed"""
        # Remove nested fields we've already handled
        direct_fields = validated_data.copy()
        for field in ['addresses', 'bank_details', 'verification_documents', 'business_preferences', 'company']:
            if field in direct_fields:
                direct_fields.pop(field)
        
        # Update only fields that are present in the request
        for field, value in direct_fields.items():
            # Only update if value has changed
            current_value = getattr(instance, field)
            if current_value != value:
                print(f"Updating field {field} from {current_value} to {value}")
                setattr(instance, field, value)

    def _handle_addresses(self, instance, addresses_data):
        """Update only addresses that have changed, add new ones, leave others untouched"""
        # Parse JSON if needed
        if isinstance(addresses_data, str):
            try:
                addresses_data = json.loads(addresses_data)
            except json.JSONDecodeError:
                addresses_data = []
                
        # Handle list wrapping
        if isinstance(addresses_data, list) and len(addresses_data) > 0 and isinstance(addresses_data[0], list):
            addresses_data = addresses_data[0]
            
        if isinstance(addresses_data, dict):
            addresses_data = [addresses_data]
            
        # Keep track of processed address IDs to avoid deleting addresses not in the current request
        processed_ids = []
        
        # Process each address in the request
        for address_data in addresses_data:
            address_id = address_data.get('id')
            
            if address_id:
                # Update existing address if it has any changed fields
                try:
                    address = Address.objects.get(id=address_id)
                    changed = False
                    
                    # Only update fields that have changed
                    for key, value in address_data.items():
                        if key != 'id' and getattr(address, key) != value:
                            setattr(address, key, value)
                            changed = True
                    
                    if changed:
                        address.save()
                        print(f"Updated address {address_id} with changed fields")
                    
                    # Make sure the address is associated with this profile
                    if not instance.addresses.filter(id=address_id).exists():
                        instance.addresses.add(address)
                        
                    processed_ids.append(address_id)
                    
                except Address.DoesNotExist:
                    # Create new address if ID not found
                    address_data_copy = address_data.copy()
                    address_data_copy.pop('id')
                    new_address = Address.objects.create(**address_data_copy)
                    instance.addresses.add(new_address)
                    processed_ids.append(new_address.id)
                    print(f"Created new address {new_address.id} (ID {address_id} not found)")
            else:
                # Create brand new address
                if 'id' in address_data:
                    address_data.pop('id')
                
                new_address = Address.objects.create(**address_data)
                instance.addresses.add(new_address)
                processed_ids.append(new_address.id)
                print(f"Created new address {new_address.id}")
                
        # NOTE: We're NOT removing existing addresses that weren't mentioned in this request
        # This is intentional to prevent data loss - if you want to remove an address, 
        # you should do that through a separate endpoint

    def _handle_bank_details(self, instance, bank_details_data):
        """Update bank details only if fields have changed"""
        if isinstance(bank_details_data, str):
            try:
                bank_details_data = json.loads(bank_details_data)
            except json.JSONDecodeError:
                return
                
        if not bank_details_data:
            return
            
        bank_id = bank_details_data.get('id')
        
        if bank_id and instance.bank_details and instance.bank_details.id == bank_id:
            # Update existing bank details if any fields changed
            changed = False
            for key, value in bank_details_data.items():
                if key != 'id' and getattr(instance.bank_details, key) != value:
                    setattr(instance.bank_details, key, value)
                    changed = True
                    
            if changed:
                instance.bank_details.save()
                print(f"Updated bank details {bank_id} with changed fields")
        else:
            # Create new bank details
            if 'id' in bank_details_data:
                bank_details_data.pop('id')
                
            bank_details = BankDetails.objects.create(**bank_details_data)
            instance.bank_details = bank_details
            print(f"Created new bank details {bank_details.id}")

    def _handle_company(self, instance, company_data):
        """Update company details only if fields have changed"""
        try:
            if isinstance(company_data, str):
                try:
                    company_data = json.loads(company_data)
                except json.JSONDecodeError:
                    return

            if not company_data:
                return

            company_id = company_data.get('id')
            print(f"Processing company data with ID: {company_id}")

            # Remove id from data to be used for update/create
            if 'id' in company_data:
                company_data.pop('id')

            # Convert registration_date to proper format if present
            if 'registration_date' in company_data and company_data['registration_date']:
                try:
                    company_data['registration_date'] = datetime.strptime(
                        company_data['registration_date'], 
                        "%Y-%m-%d"
                    ).date()
                except ValueError:
                    print("Invalid registration_date format")

            if company_id and instance.company and instance.company.id == company_id:
                # Update existing company if any fields changed
                changed = False
                for key, value in company_data.items():
                    if hasattr(instance.company, key):
                        current_value = getattr(instance.company, key)
                        if current_value != value:
                            setattr(instance.company, key, value)
                            changed = True
                            print(f"Updating company field {key} from {current_value} to {value}")

                if changed:
                    instance.company.save()
                    print(f"Updated existing company {company_id}")
            else:
                # If there's an existing company with this ID
                if company_id:
                    try:
                        company = CompanyDetails.objects.get(id=company_id)
                        # Update existing company
                        for key, value in company_data.items():
                            if hasattr(company, key):
                                setattr(company, key, value)
                        company.save()
                        instance.company = company
                        print(f"Linked existing company {company_id} to profile")
                    except CompanyDetails.DoesNotExist:
                        # Create new company if ID not found
                        company = CompanyDetails.objects.create(**company_data)
                        instance.company = company
                        print(f"Created new company {company.id} (ID {company_id} not found)")
                else:
                    # Create new company without ID
                    company = CompanyDetails.objects.create(**company_data)
                    instance.company = company
                    print(f"Created new company {company.id}")

            instance.save()  # Save the profile to update the company relationship

        except Exception as e:
            print(f"Error handling company data: {str(e)}")
            raise serializers.ValidationError(f"Error handling company data: {str(e)}")

    def _handle_verification_docs(self, instance, verification_docs_data):
        """Handle verification documents with proper file handling"""
        try:
            if isinstance(verification_docs_data, str):
                try:
                    verification_docs_data = json.loads(verification_docs_data)
                except json.JSONDecodeError:
                    verification_docs_data = []

            if isinstance(verification_docs_data, dict):
                verification_docs_data = [verification_docs_data]

            # Keep track of processed document IDs
            processed_ids = []
            existing_doc_ids = set(instance.verification_documents.values_list('id', flat=True))
            
            # Get files from request context
            request = self.context.get('request')
            files = request.FILES if request else None
            
            print(f"Available files: {list(files.keys()) if files else 'None'}")

            for doc_data in verification_docs_data:
                doc_id = doc_data.get('id')
                temp_id = doc_data.get('temp_id')
                
                # Create document identifier for file lookup
                doc_identifier = doc_id or temp_id or f"temp_{hash(str(doc_data))}"
                file_key = f'document_file_{doc_identifier}'
                
                # Try to get the file from request.FILES
                document_file = files.get(file_key) if files else None
                print(f"Looking for file with key {file_key}: {'Found' if document_file else 'Not found'}")
                
                if document_file:
                    # Store the file in doc_data for document creation/update
                    doc_data['document_file'] = document_file
                
                # Now process the document with or without file
                if doc_id and not isinstance(doc_id, str):  # Existing document with numeric id
                    try:
                        doc = VerificationDocument.objects.get(id=doc_id)
                        changed = False

                        # Update fields
                        for key, value in doc_data.items():
                            if key not in ['id', 'temp_id', 'document_file'] and getattr(doc, key) != value:
                                setattr(doc, key, value)
                                changed = True

                        # Save file if present
                        if document_file:
                            doc.document_file.save(
                                document_file.name,
                                document_file,
                                save=False
                            )
                            changed = True

                        if changed:
                            doc.save()

                        # Ensure doc is associated with profile
                        if not instance.verification_documents.filter(id=doc_id).exists():
                            instance.verification_documents.add(doc)
                        
                        processed_ids.append(doc_id)
                        existing_doc_ids.discard(doc_id)
                    except VerificationDocument.DoesNotExist:
                        # Create new doc if ID not found
                        clean_data = {k: v for k, v in doc_data.items() if k not in ['id', 'temp_id']}
                        new_doc = self._create_verification_document(clean_data)
                        instance.verification_documents.add(new_doc)
                        processed_ids.append(new_doc.id)
                else:
                    # Create new document (remove id/temp_id if present)
                    clean_data = {k: v for k, v in doc_data.items() if k not in ['id', 'temp_id']}
                    new_doc = self._create_verification_document(clean_data)
                    instance.verification_documents.add(new_doc)
                    processed_ids.append(new_doc.id)

                # Remove documents that were deleted in the frontend
                if existing_doc_ids:
                    instance.verification_documents.filter(id__in=existing_doc_ids).delete()

            return processed_ids

        except Exception as e:
            print(f"Error handling verification documents: {str(e)}")
            import traceback
            traceback.print_exc()
            raise serializers.ValidationError(f"Error handling verification documents: {str(e)}")

    def _create_verification_document(self, doc_data):
        """Helper method to create a new verification document"""
        try:
            # Extract the file from doc_data
            document_file = doc_data.pop('document_file', None)
            
            # Create document without file first
            new_doc = VerificationDocument.objects.create(**doc_data)
            
            # Handle file upload separately if present
            if document_file:
                print(f"Saving file {document_file.name} to document {new_doc.id}")
                new_doc.document_file.save(document_file.name, document_file, save=True)
            
            return new_doc
        except Exception as e:
            print(f"Error creating verification document: {str(e)}")
            import traceback
            traceback.print_exc()
            raise serializers.ValidationError(f"Error creating verification document: {str(e)}")

    def _handle_business_preferences(self, instance, business_prefs, validated_data):
        """Update business preferences from both sources"""
        if isinstance(business_prefs, str):
            try:
                business_prefs = json.loads(business_prefs)
            except json.JSONDecodeError:
                business_prefs = {}
                
        # Direct business_preferences from validated_data if present
        business_prefs_validated = validated_data.pop('business_preferences', {}) if 'business_preferences' in validated_data else {}
        
        # Combine both sources
        all_prefs = {**business_prefs, **business_prefs_validated}
        
        # Only update preferences fields that are present
        if 'preferred_payment_method' in all_prefs and instance.preferred_payment_method != all_prefs.get('preferred_payment_method'):
            instance.preferred_payment_method = all_prefs.get('preferred_payment_method')
            
        if 'budget_range' in all_prefs and instance.budget_range != all_prefs.get('budget_range'):
            instance.budget_range = all_prefs.get('budget_range')
            
        if 'project_preferences' in all_prefs and instance.project_preferences != all_prefs.get('project_preferences'):
            instance.project_preferences = all_prefs.get('project_preferences')

    def _handle_related_objects(self, manager, data, model_class):
        """Helper method to handle related objects (addresses, bank details, etc.)"""
        print(f"Original {model_class.__name__} data:", data)  # Debug log
        
        # Handle nested list structure
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            data = data[0]  # Unwrap the outer list
        
        # Parse JSON strings if needed
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = []
        
        print(f"Processed {model_class.__name__} data:", data)  # Debug log

        # Create or update objects
        for item_data in data:
            print("Step2 item_data",item_data)
            if isinstance(item_data, dict):
                print("Step1 item_data",item_data)
                try:
                    item_id = item_data.get('id')
                    
                    if item_id:
                        print("item_id",item_id)
                        # Try to update existing object
                        try:
                            item = model_class.objects.get(id=item_id)
                            print("item",item)
                            for key, value in item_data.items():
                                setattr(item, key, value)
                            item.save()
                            print(f"Updated existing {model_class.__name__}:", item.id)
                        except model_class.DoesNotExist:
                            # If object with given ID doesn't exist, create new
                            item_data.pop('id')
                            print("item_data not there",item_data.pop('id'))
                            item = model_class.objects.create(**item_data)
                            print(f"Created new {model_class.__name__} (ID not found):", item.id)
                    else:
                        # Create new object without ID
                        if 'id' in item_data:
                            item_data.pop('id')
                        item = model_class.objects.create(**item_data)
                        print(f"Created new {model_class.__name__}:", item.id)
                    
                    # Important: Add the item to the manager
                    manager.add(item)
                    print(f"Added {model_class.__name__} {item.id} to manager")
                    
                except Exception as e:
                    print(f"Error handling {model_class.__name__}: {str(e)}")
                    raise serializers.ValidationError(f"Error handling {model_class.__name__}: {str(e)}")


class FreelancerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreelancerProfile
        fields = '__all__'

class ClientFeedbackSerializer(serializers.ModelSerializer):
    from_user_username = serializers.CharField(source='from_user.username', read_only=True)
    from_user_role = serializers.CharField(source='from_user.role', read_only=True)
    to_user_username = serializers.CharField(source='to_user.username', read_only=True)
    to_user_role = serializers.CharField(source='to_user.role', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = [
            'id',
            'from_user',  # Foreign key relation (if needed)
            'from_user_role',  # Foreign key relation (if needed)
            'to_user',  # Foreign key relation (if needed)
            'to_user_role',  # Foreign key relation (if needed)
            'from_user_username',  # Freelancer's username
            'to_user_username',  # Freelancer's username
            'rating',  # Rating for the review
            'feedback',  # Review text
            'created_at',  # Date the review was created
            'project_title',  # Project title associated with the review
            'parent_feedback',  # The parent feedback (for replies)
            'replies',  # Nested replies
        ]
        read_only_fields = ['from_user_username', 'project_title', 'parent_feedback']

    def get_replies(self, obj):
        # Only include direct replies, and avoid infinite recursion.
        if obj.parent_feedback:
            return []  # Don't serialize replies for replies.
        
        replies = obj.replies.all()
        return ClientFeedbackSerializer(replies, many=True).data


class UserProfileSerializer(serializers.Serializer):
    def to_representation(self, instance):
        # Check if the user is a freelancer
        if instance.role == 'freelancer':
            try:
                profile = FreelancerProfile.objects.get(user=instance)
                user_name = instance.username
                result = {
                    'user_name': user_name,
                    'id': instance.id,
                    'bio': profile.bio,  # Get bio from FreelancerProfile
                    'profile_picture': profile.profile_picture.url if profile.profile_picture else None,  # Get profile picture
                    'rating': profile.average_rating,  # Freelancer rating
                }
                return result
            except FreelancerProfile.DoesNotExist:
                # Return an empty dictionary or a default profile if it does not exist
                return {"message": "Freelancer profile not found"}
        
        # Check if the user is a client
        elif instance.role == 'client':
            try:
                profile = ClientProfile.objects.get(user=instance)
                user_name = instance.username
                result = {
                    'user_name': user_name,
                    'id': instance.id,
                    'bio': profile.bio,  # Get bio from ClientProfile
                    'profile_picture': profile.profile_picture.url if profile.profile_picture else None,  # Get profile picture
                    'company': profile.company_name,  # Client's company name
                }
                return result
            except ClientProfile.DoesNotExist:
                # Return an empty dictionary or a default profile if it does not exist
                return {"message": "Client profile not found"}
        
        # Default case if the user has no role or something unexpected
        return {"message": "Profile data unavailable"}

def get_user_profile(user):
    # First, check if user is None
    if not user:
        return {
            "user_name": "Unknown",
            "user_id": None,
            "bio": "",
            "company": "",
            "rating": 0,
            "role": "unknown"
        }
        
    if user.role == 'client':
        # Check if 'client_profile' exists
        try:
            client_profile = ClientProfile.objects.get(user=user)
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": client_profile.bio if client_profile.bio else "",  
                "company": client_profile.company_name if hasattr(client_profile, 'company_name') else "",
                "rating": client_profile.average_rating if hasattr(client_profile, 'average_rating') else 0,
                "role": user.role
            }
        except ClientProfile.DoesNotExist:
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": "",
                "company": "",
                "rating": 0,
                "role": user.role
            }

    elif user.role == 'freelancer' or user.role == 'student':  # Added student role check
        # Check if 'freelancer_profile' exists
        try:
            freelancer_profile = FreelancerProfile.objects.get(user=user)
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": freelancer_profile.bio if freelancer_profile.bio else "",
                "company": freelancer_profile.company_name if hasattr(freelancer_profile, 'company_name') else "",
                "rating": freelancer_profile.average_rating if hasattr(freelancer_profile, 'average_rating') else 0,
                "role": user.role
            }
        except FreelancerProfile.DoesNotExist:
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": "",
                "company": "",
                "rating": 0,
                "role": user.role
            }
    
    # Default case if the user has no role or unexpected role
    return {
        "user_name": user.username,
        "user_id": user.id,
        "bio": "",
        "company": "",
        "rating": 0,
        "role": user.role if hasattr(user, 'role') else "unknown"
    }


class ConnectionSendinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Connection
        fields = ['from_user', 'to_user', 'status', 'created_at', 'updated_at']
    
        
    def to_representation(self, instance):
        # Get the original representation
        representation = super().to_representation(instance)

        # Extract the 'from_user' and 'to_user'
        from_user = instance.from_user
        to_user = instance.to_user

        # Helper function to get the profile data
        print("from_user",from_user)
        print("to_user",to_user)
        # Determine which user to return (opposite user based on who the current user is)
        current_user = self.context.get('request').user
        print("current_user",current_user)
        if current_user == from_user:
            opposite_user = to_user
        else:
            opposite_user = from_user
        print("opposite_user",opposite_user)
        # Get the profile of the opposite user
        opposite_user_profile = get_user_profile(opposite_user)
        print("opposite_user_profile",opposite_user_profile)
        # Return the response with the opposite user's profile and connection details
        return {
            "id":instance.id,
            "user_name": opposite_user_profile.get('user_name'),
            "user_id": opposite_user_profile.get('user_id'),
            "company": opposite_user_profile.get('company'),
            "rating": opposite_user_profile.get('rating'),
            "bio": opposite_user_profile.get('bio'),
            "role": opposite_user_profile.get('role'),
            "status": representation.get('status'),
            "created_at": representation.get('created_at'),
            "updated_at": representation.get('updated_at')
        }
    

class ConnectionRequestSerializer(serializers.ModelSerializer):
    from_user_username = serializers.CharField(source='from_user.username', read_only=True)

    class Meta:
        model = Connection
        fields = ['from_user','from_user_username','id', 'status', 'created_at', 'updated_at']
from rest_framework import serializers
from .models import ClientProfile,FreelancerProfile,Feedback, Address, CompanyDetails,BankDetails,VerificationDocument
from core.models import Connection
from django.contrib.auth import get_user_model
import json
from datetime import datetime
from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status

User = get_user_model()  # This will point to your custom User model if defined

class VerificationDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = VerificationDocument
        fields = '__all__'

    def update(self, instance, validated_data):
        verification_documents_data = self.initial_data.get('verification_documents', [])
        
        try:
            # Handle existing documents
            existing_docs = {doc.id: doc for doc in instance.verification_documents.all()}
            
            for doc_data in verification_documents_data:
                doc_id = doc_data.get('id')
                if doc_id and doc_id in existing_docs:
                    # Update existing document
                    doc = existing_docs[doc_id]
                    for field, value in doc_data.items():
                        setattr(doc, field, value)
                    doc.save()
                else:
                    # Create new document
                    VerificationDocument.objects.create(
                        client_profile=instance,
                        **{k: v for k, v in doc_data.items() if k != 'id'}
                    )
            
            # Delete documents that were removed
            kept_ids = [doc.get('id') for doc in verification_documents_data if doc.get('id')]
            instance.verification_documents.exclude(id__in=kept_ids).delete()
            
        except Exception as e:
            raise serializers.ValidationError(f"Error handling verification documents: {str(e)}")
        
        return super().update(instance, validated_data)


class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = '__all__'

class BankDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankDetails
        fields = '__all__'

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'
        extra_kwargs = {
            'street_address': {'required': True},
            'city': {'required': True},
            'state': {'required': True},
            'country': {'required': True},
            'postal_code': {'required': True},
            'address_type': {'required': False, 'default': 'registered'},
            'is_primary': {'required': False, 'default': False},
            'verified': {'required': False, 'default': False}
        }

class CompanyDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyDetails
        fields = '__all__'

class ClientProfilePartialUpdateSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='user.username', read_only=True)
    addresses = AddressSerializer(many=True, required=False)
    bank_details = BankDetailsSerializer(required=False)
    verification_documents = serializers.ListField(required=False, allow_empty=True)
    business_preferences = serializers.DictField(required=False, allow_empty=True)
    company = CompanyDetailsSerializer(required=False)

    class Meta:
        model = ClientProfile
        fields = [
            'name', 'bio', 'description', 'profile_picture', 'cover_photo', 'gender', 'dob',
            'primary_email', 'secondary_email', 'phone_number', 'alternate_phone',
            'addresses', 'bank_details', 'verification_documents', 'business_preferences',
            'email_verified', 'phone_verified', 'identity_verified', 'profile_status',
            'account_tier', 'terms_accepted', 'privacy_policy_accepted',
            'preferred_payment_method', 'budget_range', 'company'
        ]

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Include bank details in the response
        if instance.bank_details:
            ret['bank_details'] = {
                'id': instance.bank_details.id,
                'bank_name': instance.bank_details.bank_name,
                'account_number': instance.bank_details.account_number,
                'ifsc_code': instance.bank_details.ifsc_code,
                'account_holder_name': instance.bank_details.account_holder_name,
                'branch_name': instance.bank_details.branch_name,
                'swift_code': instance.bank_details.swift_code,
                'primary': instance.bank_details.primary
            }
        return ret

    def update(self, instance, validated_data):
        try:
            print("Starting optimized update method in serializer")
            
            # Extract nested data from initial_data (not validated_data)
            addresses_data = self.initial_data.get('addresses')
            bank_details_data = self.initial_data.get('bank_details')
            verification_docs_data = self.initial_data.get('verification_documents')
            company_data = self.initial_data.get('company')
            business_prefs_data = self.initial_data.get('business_preferences')
            
            # HANDLE ADDRESSES - only if present in request
            if addresses_data:
                self._handle_addresses(instance, addresses_data)
                
            # HANDLE BANK DETAILS - only if present in request
            if bank_details_data:
                self._handle_bank_details(instance, bank_details_data)

            # HANDLE COMPANY DETAILS - only if present in request
            if company_data:
                self._handle_company(instance, company_data)

            # HANDLE VERIFICATION DOCUMENTS - only if present in request
            if verification_docs_data:
                self._handle_verification_docs(instance, verification_docs_data)

            # HANDLE BUSINESS PREFERENCES - only if present in request
            if business_prefs_data:
                self._handle_business_preferences(instance, business_prefs_data, validated_data)

            # Update direct fields from validated_data if they exist and have changed
            self._update_direct_fields(instance, validated_data)

            instance.save()
            print("Profile updated successfully in serializer")
            return instance

        except Exception as e:
            print(f"Error in serializer update method: {str(e)}")
            raise serializers.ValidationError(f"Error updating profile: {str(e)}")

    def _update_direct_fields(self, instance, validated_data):
        """Only update direct fields if they have changed"""
        # Remove nested fields we've already handled
        direct_fields = validated_data.copy()
        for field in ['addresses', 'bank_details', 'verification_documents', 'business_preferences', 'company']:
            if field in direct_fields:
                direct_fields.pop(field)
        
        # Update only fields that are present in the request
        for field, value in direct_fields.items():
            # Special handling for date fields
            if field == 'dob' and value:
                try:
                    # Convert string date to Python date object
                    if isinstance(value, str):
                        value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    print(f"Invalid date format for DOB: {value}")
                    continue
                
            # Only update if value has changed
            current_value = getattr(instance, field)
            if current_value != value:
                print(f"Updating field {field} from {current_value} to {value}")
                setattr(instance, field, value)
    def _handle_addresses(self, instance, addresses_data):
        """Update only addresses that have changed, add new ones, leave others untouched"""
        # Parse JSON if needed
        if isinstance(addresses_data, str):
            try:
                addresses_data = json.loads(addresses_data)
            except json.JSONDecodeError:
                addresses_data = []
                
        # Handle list wrapping
        if isinstance(addresses_data, list) and len(addresses_data) > 0 and isinstance(addresses_data[0], list):
            addresses_data = addresses_data[0]
            
        if isinstance(addresses_data, dict):
            addresses_data = [addresses_data]
            
        # Keep track of processed address IDs to avoid deleting addresses not in the current request
        processed_ids = []
        
        # Process each address in the request
        for address_data in addresses_data:
            address_id = address_data.get('id')
            
            if address_id:
                # Update existing address if it has any changed fields
                try:
                    address = Address.objects.get(id=address_id)
                    changed = False
                    
                    # Only update fields that have changed
                    for key, value in address_data.items():
                        if key != 'id' and getattr(address, key) != value:
                            setattr(address, key, value)
                            changed = True
                    
                    if changed:
                        address.save()
                        print(f"Updated address {address_id} with changed fields")
                    
                    # Make sure the address is associated with this profile
                    if not instance.addresses.filter(id=address_id).exists():
                        instance.addresses.add(address)
                        
                    processed_ids.append(address_id)
                    
                except Address.DoesNotExist:
                    # Create new address if ID not found
                    address_data_copy = address_data.copy()
                    address_data_copy.pop('id')
                    new_address = Address.objects.create(**address_data_copy)
                    instance.addresses.add(new_address)
                    processed_ids.append(new_address.id)
                    print(f"Created new address {new_address.id} (ID {address_id} not found)")
            else:
                # Create brand new address
                if 'id' in address_data:
                    address_data.pop('id')
                
                new_address = Address.objects.create(**address_data)
                instance.addresses.add(new_address)
                processed_ids.append(new_address.id)
                print(f"Created new address {new_address.id}")
                
        # NOTE: We're NOT removing existing addresses that weren't mentioned in this request
        # This is intentional to prevent data loss - if you want to remove an address, 
        # you should do that through a separate endpoint

    def _handle_bank_details(self, instance, bank_details_data):
        """Update bank details only if fields have changed"""
        if isinstance(bank_details_data, str):
            try:
                bank_details_data = json.loads(bank_details_data)
            except json.JSONDecodeError:
                return
                
        if not bank_details_data:
            return
            
        bank_id = bank_details_data.get('id')
        
        if bank_id and instance.bank_details and instance.bank_details.id == bank_id:
            # Update existing bank details if any fields changed
            changed = False
            for key, value in bank_details_data.items():
                if key != 'id' and getattr(instance.bank_details, key) != value:
                    setattr(instance.bank_details, key, value)
                    changed = True
                    
            if changed:
                instance.bank_details.save()
                print(f"Updated bank details {bank_id} with changed fields")
        else:
            # Create new bank details
            if 'id' in bank_details_data:
                bank_details_data.pop('id')
                
            bank_details = BankDetails.objects.create(**bank_details_data)
            instance.bank_details = bank_details
            print(f"Created new bank details {bank_details.id}")

    def _handle_company(self, instance, company_data):
        """Update company details only if fields have changed"""
        try:
            if isinstance(company_data, str):
                try:
                    company_data = json.loads(company_data)
                except json.JSONDecodeError:
                    return

            if not company_data:
                return

            company_id = company_data.get('id')
            print(f"Processing company data with ID: {company_id}")

            # Remove id from data to be used for update/create
            if 'id' in company_data:
                company_data.pop('id')

            # Convert registration_date to proper format if present
            if 'registration_date' in company_data and company_data['registration_date']:
                try:
                    company_data['registration_date'] = datetime.strptime(
                        company_data['registration_date'], 
                        "%Y-%m-%d"
                    ).date()
                except ValueError:
                    print("Invalid registration_date format")

            if company_id and instance.company and instance.company.id == company_id:
                # Update existing company if any fields changed
                changed = False
                for key, value in company_data.items():
                    if hasattr(instance.company, key):
                        current_value = getattr(instance.company, key)
                        if current_value != value:
                            setattr(instance.company, key, value)
                            changed = True
                            print(f"Updating company field {key} from {current_value} to {value}")

                if changed:
                    instance.company.save()
                    print(f"Updated existing company {company_id}")
            else:
                # If there's an existing company with this ID
                if company_id:
                    try:
                        company = CompanyDetails.objects.get(id=company_id)
                        # Update existing company
                        for key, value in company_data.items():
                            if hasattr(company, key):
                                setattr(company, key, value)
                        company.save()
                        instance.company = company
                        print(f"Linked existing company {company_id} to profile")
                    except CompanyDetails.DoesNotExist:
                        # Create new company if ID not found
                        company = CompanyDetails.objects.create(**company_data)
                        instance.company = company
                        print(f"Created new company {company.id} (ID {company_id} not found)")
                else:
                    # Create new company without ID
                    company = CompanyDetails.objects.create(**company_data)
                    instance.company = company
                    print(f"Created new company {company.id}")

            instance.save()  # Save the profile to update the company relationship

        except Exception as e:
            print(f"Error handling company data: {str(e)}")
            raise serializers.ValidationError(f"Error handling company data: {str(e)}")

    # In profileViews.py, modify the _handle_verification_docs method:
    def _handle_verification_docs(self, instance, verification_docs_data):
        
            if isinstance(verification_docs_data, str):
                try:
                    verification_docs_data = json.loads(verification_docs_data)
                except json.JSONDecodeError:
                    verification_docs_data = []

            # Get files from request context
            request = self.context.get('request')
            files = request.FILES if request else None

            print(f"Available files: {list(files.keys()) if files else 'None'}")
            print(f"Verification docs data: {verification_docs_data}")

            for doc_data in verification_docs_data:
                doc_id = doc_data.get('id')
                temp_id = doc_data.get('temp_id')

                # Create document identifier for file lookup
                doc_identifier = doc_id or temp_id
                file_key = f'document_file_{doc_identifier}'

                print(f"Looking for file with key: {file_key}")

                # Try to get the file from request.FILES
                document_file = files.get(file_key) if files else None
                print(f"File found: {document_file is not None}")
    def _create_verification_document(self, doc_data):
        """Helper method to create a new verification document"""
        try:
            # Extract the file from doc_data
            document_file = doc_data.pop('document_file', None)
            
            # Create document without file first
            new_doc = VerificationDocument.objects.create(**doc_data)
            
            # Handle file upload separately if present
            if document_file:
                print(f"Saving file {document_file.name} to document {new_doc.id}")
                new_doc.document_file.save(document_file.name, document_file, save=True)
            
            return new_doc
        except Exception as e:
            print(f"Error creating verification document: {str(e)}")
            import traceback
            traceback.print_exc()
            raise serializers.ValidationError(f"Error creating verification document: {str(e)}")

    def _handle_business_preferences(self, instance, business_prefs, validated_data):
        """Update business preferences from both sources"""
        if isinstance(business_prefs, str):
            try:
                business_prefs = json.loads(business_prefs)
            except json.JSONDecodeError:
                business_prefs = {}
                
        # Direct business_preferences from validated_data if present
        business_prefs_validated = validated_data.pop('business_preferences', {}) if 'business_preferences' in validated_data else {}
        
        # Combine both sources
        all_prefs = {**business_prefs, **business_prefs_validated}
        
        # Only update preferences fields that are present
        if 'preferred_payment_method' in all_prefs and instance.preferred_payment_method != all_prefs.get('preferred_payment_method'):
            instance.preferred_payment_method = all_prefs.get('preferred_payment_method')
            
        if 'budget_range' in all_prefs and instance.budget_range != all_prefs.get('budget_range'):
            instance.budget_range = all_prefs.get('budget_range')
            
        if 'project_preferences' in all_prefs and instance.project_preferences != all_prefs.get('project_preferences'):
            instance.project_preferences = all_prefs.get('project_preferences')

    def _handle_related_objects(self, manager, data, model_class):
        """Helper method to handle related objects (addresses, bank details, etc.)"""
        print(f"Original {model_class.__name__} data:", data)  # Debug log
        
        # Handle nested list structure
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
            data = data[0]  # Unwrap the outer list
        
        # Parse JSON strings if needed
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = []
        
        print(f"Processed {model_class.__name__} data:", data)  # Debug log

        # Create or update objects
        for item_data in data:
            print("Step2 item_data",item_data)
            if isinstance(item_data, dict):
                print("Step1 item_data",item_data)
                try:
                    item_id = item_data.get('id')
                    
                    if item_id:
                        print("item_id",item_id)
                        # Try to update existing object
                        try:
                            item = model_class.objects.get(id=item_id)
                            print("item",item)
                            for key, value in item_data.items():
                                setattr(item, key, value)
                            item.save()
                            print(f"Updated existing {model_class.__name__}:", item.id)
                        except model_class.DoesNotExist:
                            # If object with given ID doesn't exist, create new
                            item_data.pop('id')
                            print("item_data not there",item_data.pop('id'))
                            item = model_class.objects.create(**item_data)
                            print(f"Created new {model_class.__name__} (ID not found):", item.id)
                    else:
                        # Create new object without ID
                        if 'id' in item_data:
                            item_data.pop('id')
                        item = model_class.objects.create(**item_data)
                        print(f"Created new {model_class.__name__}:", item.id)
                    
                    # Important: Add the item to the manager
                    manager.add(item)
                    print(f"Added {model_class.__name__} {item.id} to manager")
                    
                except Exception as e:
                    print(f"Error handling {model_class.__name__}: {str(e)}")
                    raise serializers.ValidationError(f"Error handling {model_class.__name__}: {str(e)}")


class FreelancerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = FreelancerProfile
        fields = '__all__'

class ClientFeedbackSerializer(serializers.ModelSerializer):
    from_user_username = serializers.CharField(source='from_user.username', read_only=True)
    from_user_role = serializers.CharField(source='from_user.role', read_only=True)
    to_user_username = serializers.CharField(source='to_user.username', read_only=True)
    to_user_role = serializers.CharField(source='to_user.role', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)
    
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = [
            'id',
            'from_user',  # Foreign key relation (if needed)
            'from_user_role',  # Foreign key relation (if needed)
            'to_user',  # Foreign key relation (if needed)
            'to_user_role',  # Foreign key relation (if needed)
            'from_user_username',  # Freelancer's username
            'to_user_username',  # Freelancer's username
            'rating',  # Rating for the review
            'feedback',  # Review text
            'created_at',  # Date the review was created
            'project_title',  # Project title associated with the review
            'parent_feedback',  # The parent feedback (for replies)
            'replies',  # Nested replies
        ]
        read_only_fields = ['from_user_username', 'project_title', 'parent_feedback']

    def get_replies(self, obj):
        # Only include direct replies, and avoid infinite recursion.
        if obj.parent_feedback:
            return []  # Don't serialize replies for replies.
        
        replies = obj.replies.all()
        return ClientFeedbackSerializer(replies, many=True).data


class UserProfileSerializer(serializers.Serializer):
    def to_representation(self, instance):
        # Check if the user is a freelancer
        if instance.role == 'freelancer':
            try:
                profile = FreelancerProfile.objects.get(user=instance)
                user_name = instance.username
                result = {
                    'user_name': user_name,
                    'id': instance.id,
                    'bio': profile.bio,  # Get bio from FreelancerProfile
                    'profile_picture': profile.profile_picture.url if profile.profile_picture else None,  # Get profile picture
                    'rating': profile.average_rating,  # Freelancer rating
                }
                return result
            except FreelancerProfile.DoesNotExist:
                # Return an empty dictionary or a default profile if it does not exist
                return {"message": "Freelancer profile not found"}
        
        # Check if the user is a client
        elif instance.role == 'client':
            try:
                profile = ClientProfile.objects.get(user=instance)
                user_name = instance.username
                result = {
                    'user_name': user_name,
                    'id': instance.id,
                    'bio': profile.bio,  # Get bio from ClientProfile
                    'profile_picture': profile.profile_picture.url if profile.profile_picture else None,  # Get profile picture
                    'company': profile.company_name,  # Client's company name
                }
                return result
            except ClientProfile.DoesNotExist:
                # Return an empty dictionary or a default profile if it does not exist
                return {"message": "Client profile not found"}
        
        # Default case if the user has no role or something unexpected
        return {"message": "Profile data unavailable"}

def get_user_profile(user):
    # First, check if user is None
    if not user:
        return {
            "user_name": "Unknown",
            "user_id": None,
            "bio": "",
            "company": "",
            "rating": 0,
            "role": "unknown"
        }
        
    if user.role == 'client':
        # Check if 'client_profile' exists
        try:
            client_profile = ClientProfile.objects.get(user=user)
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": client_profile.bio if client_profile.bio else "",  
                "company": client_profile.company_name if hasattr(client_profile, 'company_name') else "",
                "rating": client_profile.average_rating if hasattr(client_profile, 'average_rating') else 0,
                "role": user.role
            }
        except ClientProfile.DoesNotExist:
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": "",
                "company": "",
                "rating": 0,
                "role": user.role
            }

    elif user.role == 'freelancer' or user.role == 'student':  # Added student role check
        # Check if 'freelancer_profile' exists
        try:
            freelancer_profile = FreelancerProfile.objects.get(user=user)
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": freelancer_profile.bio if freelancer_profile.bio else "",
                "company": freelancer_profile.company_name if hasattr(freelancer_profile, 'company_name') else "",
                "rating": freelancer_profile.average_rating if hasattr(freelancer_profile, 'average_rating') else 0,
                "role": user.role
            }
        except FreelancerProfile.DoesNotExist:
            return {
                "user_name": user.username,
                "user_id": user.id,
                "bio": "",
                "company": "",
                "rating": 0,
                "role": user.role
            }
    
    # Default case if the user has no role or unexpected role
    return {
        "user_name": user.username,
        "user_id": user.id,
        "bio": "",
        "company": "",
        "rating": 0,
        "role": user.role if hasattr(user, 'role') else "unknown"
    }


class ConnectionSendinSerializer(serializers.ModelSerializer):
    class Meta:
        model = Connection
        fields = ['from_user', 'to_user', 'status', 'created_at', 'updated_at']
    
        
    def to_representation(self, instance):
        # Get the original representation
        representation = super().to_representation(instance)

        # Extract the 'from_user' and 'to_user'
        from_user = instance.from_user
        to_user = instance.to_user

        # Determine which user to return (opposite user based on who the current user is)
        current_user = self.context.get('request').user if self.context.get('request') else None
        
        if current_user == from_user:
            opposite_user = to_user
        else:
            opposite_user = from_user
        
        # Get the profile of the opposite user
        opposite_user_profile = get_user_profile(opposite_user)
        
        # Return the response with the opposite user's profile and connection details
        return {
            "id": instance.id,
            "user_name": opposite_user_profile.get('user_name', 'Unknown'),
            "user_id": opposite_user_profile.get('user_id'),
            "company": opposite_user_profile.get('company', ''),
            "rating": opposite_user_profile.get('rating', 0),
            "bio": opposite_user_profile.get('bio', ''),
            "role": opposite_user_profile.get('role', 'unknown'),
            "status": representation.get('status'),
            "created_at": representation.get('created_at'),
            "updated_at": representation.get('updated_at')
        }
    

class ConnectionRequestSerializer(serializers.ModelSerializer):
    from_user_username = serializers.CharField(source='from_user.username', read_only=True)

    class Meta:
        model = Connection
        fields = ['from_user','from_user_username','id', 'status', 'created_at', 'updated_at']

