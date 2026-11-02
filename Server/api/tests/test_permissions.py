from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, APITestCase
from rest_framework.views import APIView


class DefaultPermissionTests(APITestCase):
    def test_endpoints_require_login_by_default(self):
        class UnprotectedLookingView(APIView):
            # No permission_classes set, so the project default applies.
            def get(self, request):
                return Response({"secret": True})

        request = APIRequestFactory().get("/anything/")
        response = UnprotectedLookingView.as_view()(request)
        self.assertIn(response.status_code,
                      [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
