from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_not_required

from accounts.models import User
from .decorators import role_required
# Create your views here.


@login_not_required
def login(request):
    return render(request, "web/login.html")
