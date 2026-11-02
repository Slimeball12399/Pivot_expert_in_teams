from django.test import TestCase


class NotFoundPageTests(TestCase):
    # The test runner always runs with DEBUG off, so handler404 is used.
    def test_unknown_url_shows_pivot_404_page(self):
        response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "web/404.html")
        self.assertContains(response, "Sorry, we can't find the page you're looking for.", status_code=404)
