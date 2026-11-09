from rest_framework.exceptions import APIException


class CodedError(APIException):
    """An error with a code the app can react to, as {"detail": ..., "code": ...}.

    For example 403 {"code": "email_not_verified"} sends the app to the code
    screen. The code is the ValidationError.code from accounts.services.
    """

    status_code = 400

    def __init__(self, detail, code, status_code=None):
        super().__init__({"detail": detail, "code": code})
        if status_code is not None:
            self.status_code = status_code
