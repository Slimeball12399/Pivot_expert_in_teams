from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase


class ApiDocsTests(APITestCase):
    def test_docs_are_served(self):
        with self.subTest("OpenAPI schema lists our endpoints"):
            response = self.client.get(reverse("api:schema"), {"format": "json"})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            paths = response.json()["paths"]
            self.assertIn("/api/auth/register/", paths)
            self.assertIn("/api/health/", paths)

        with self.subTest("Swagger UI loads without a CDN"):
            response = self.client.get(reverse("api:docs"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            html = response.content.decode()
            self.assertNotIn("cdn.jsdelivr.net", html)
            self.assertIn("drf_spectacular_sidecar", html)
