from django.shortcuts import render, redirect
from django.http import HttpResponse 
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_not_required

# Create your views here.



@login_not_required
def login_view(request):

    if request.user.is_authenticated:
        return redirect("/")
    
    if request.method == "GET":
        return render(request, "login.html")

    elif request.method == "POST":

        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request,username=username,password=password)

        if user is not None:
            login(request, user)

            return redirect("home")

        else:
            return render(request, "login.html", {
                "erro": "Usuário ou senha inválidos."
            })



@login_not_required
def cadastro_view(request):

    if request.method == "GET":
        return render(request, "cadastro.html")

    elif request.method == "POST":

        name = request.POST.get("name")
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if (
            User.objects.filter(username=username).exists()
            or User.objects.filter(email=email).exists()
        ):
            return HttpResponse("Usuário ou e-mail já cadastrado!")

        else:
            User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=name
            )

            return redirect("login:login")


  
