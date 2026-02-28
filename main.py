from fastapi import FastAPI, Request, Form, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html

import os
import secrets
from dotenv import load_dotenv

##? Load environment variables from .env file
load_dotenv()
COOKIE_NAME = "yupeng_gpt_session"
AUTH_TOKEN = "yupeng_gpt_tokens"

app = FastAPI(
    title="Yupeng GPT",
    docs_url=None,     # Disable default Swagger UI, redirecting to new url
    redoc_url=None,    # Disable ReDoc UI
    openapi_url=None,  # Disable OpenAPI schema, and enable OpenAPI after logining
    debug=True
)

##? Paths for static files and templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

##? Static files
app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)
##? Jinja2 templates
templates = Jinja2Templates(directory = TEMPLATE_DIR)

##? Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], # Allow all origins
    allow_methods=['*'], # Allow all HTTP methods
    allow_headers=['*'], # Allow all headers
)

app.add_middleware(
    GZipMiddleware,
    minimum_size=1024  # Compress responses larger than 1KB
)

##? OpenAPI protect
@app.get(
    "/openapi.json",
    include_in_schema=False,
)
async def custom_openapi(
    request: Request
):
    if request.cookies.get(COOKIE_NAME) == AUTH_TOKEN:
        return JSONResponse(get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes
        ))

    return RedirectResponse(
        url="/login",
    )

##? Redirect to Swagger UI
@app.get(
    "/yupeng-gpt-docs",
    include_in_schema=False
)
async def redirect_to_swagger(
    request: Request
):
    if request.cookies.get(COOKIE_NAME) == AUTH_TOKEN:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="YupengGPT Docs"
        )
    return RedirectResponse(
        url="/login",
    )

##? Root HTML response
@app.get(
    '/',
    tags=["Root"],
    response_class=HTMLResponse
)
async def root_page(
    request: Request
):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request
        }
    )

##? Login HTML response
@app.get(
    "/login",
    tags=["Login"],
    response_class=HTMLResponse
)
async def login_page(
    request: Request
):
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request
        }
    )

##? Login POST
@app.post(
    "/login",
    tags=["Login"],
)
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    env_user = os.getenv("UESER")
    env_pwd = os.getenv("PASSWORD")
    if (env_user and env_pwd) \
        and secrets.compare_digest(username, env_user) \
        and secrets.compare_digest(password, env_pwd):

        redirect = RedirectResponse(
            url="/yupeng-gpt-docs",
            status_code=status.HTTP_302_FOUND
        )
        redirect.set_cookie(
            key=COOKIE_NAME,
            value=AUTH_TOKEN,
            httponly=True,
        )
        return redirect

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": "Invalid username or password"
        },
        status_code=status.HTTP_401_UNAUTHORIZED
    )


if __name__ == "__main__":
    import uvicorn
    file_name = __file__.split("\\")[-1].split('.')[0]
    serve_name = f"{file_name}:app"
    uvicorn.run(
        serve_name,
        host="127.0.0.1",
        port=8000,
        reload=True
    )