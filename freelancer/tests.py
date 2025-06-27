from django.test import TestCase
from django.contrib.auth import get_user_model
from OBSP.models import OBSPTemplate
from .obsp_eligibility import OBSPEligibilityEngine

# Create your tests here.

class OBSPEligibilityTest(TestCase):
    def test_level_1_eligibility(self):
        user = get_user_model().objects.create(username='testuser')
        obsp = OBSPTemplate.objects.create(title='Test OBSP', category='web-development')
        engine = OBSPEligibilityEngine(user, obsp, 'easy')
        eligible, reason = engine.check_eligibility()
        self.assertIsInstance(eligible, bool)
        self.assertIsInstance(reason, str)
