from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class HealthTests(APITestCase):
    def test_health_is_public_and_reports_database(self):
        response = self.client.get(reverse("api:health"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok", "database": "ok"})
