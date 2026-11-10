"""The shop's pages, from shop/web/, as "The frontend" in DESIGN.md says.

From tinyAmazon/: python -m tinyhttp --host 127.0.0.1 --port 8080 shop.frontend:app
"""

from tinyweb import App
from tinyweb.static import send_file

# Its CSS and JavaScript are at /static/.
app = App(__name__, static_folder="web")


@app.route("/")
def search(request):
    return send_file(request, app.static_folder, "index.html")


@app.route("/login")
def login(request):
    return send_file(request, app.static_folder, "login.html")


@app.route("/sell")
def sell(request):
    return send_file(request, app.static_folder, "sell.html")
