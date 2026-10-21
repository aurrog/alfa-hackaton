from app.api import auth, bank, client, system

ROUTERS = [system.router, auth.router, client.router, bank.router]
