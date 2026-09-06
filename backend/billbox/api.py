from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import secrets
import sqlite3
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from .auth import LoginAttemptLimiter, Session, SessionManager
from .config import Settings
from .db import Database
from .ledger import Ledger


class LoginBody(BaseModel):
    password: str = Field(min_length=1, max_length=256)


class TransactionBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    account_id: str = Field(min_length=1, max_length=80)
    category_id: str | None = Field(default=None, max_length=80)
    kind: Literal["expense", "income", "refund", "transfer", "repayment"]
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="CNY", pattern=r"^[A-Za-z]{3}$")
    merchant: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=1000)
    channel: str = Field(default="", max_length=100)
    occurred_at: datetime


class TransactionUpdateBody(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=1000)
    review_state: Literal["pending", "confirmed"] | None = None


def create_app(settings: Settings) -> FastAPI:
    database = Database(settings.database_path, settings.migrations_dir)
    database.migrate()
    ledger = Ledger(database)
    sessions = SessionManager(
        settings.session_secret, ttl_seconds=settings.session_ttl_seconds
    )
    limiter = LoginAttemptLimiter()

    app = FastAPI(title="Billbox", docs_url=None, redoc_url=None)
    app.state.database = database
    app.state.ledger = ledger
    app.state.settings = settings

    def require_session(request: Request) -> Session:
        session = sessions.verify(request.cookies.get(sessions.cookie_name))
        if session is None:
            raise HTTPException(status_code=401, detail="登录已失效，请重新登录")
        return session

    def require_csrf(
        session: Session = Depends(require_session),
        csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    ) -> Session:
        if not csrf_token or not secrets.compare_digest(
            csrf_token, session.csrf_token
        ):
            raise HTTPException(status_code=403, detail="页面令牌已失效，请刷新页面后重试")
        return session

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        if not database.healthcheck():
            raise HTTPException(status_code=503, detail="数据库完整性检查未通过")
        return {"status": "ok"}

    @app.post("/api/auth/login", status_code=204)
    def login(body: LoginBody, request: Request) -> Response:
        client_key = request.client.host if request.client else "unknown"
        if limiter.is_limited(client_key):
            raise HTTPException(status_code=429, detail="尝试次数过多，请 5 分钟后再试")
        if not secrets.compare_digest(body.password, settings.app_password):
            limiter.record_failure(client_key)
            raise HTTPException(status_code=401, detail="密码不正确，请重新输入")
        limiter.reset(client_key)
        token, _ = sessions.create()
        response = Response(status_code=204)
        response.set_cookie(
            sessions.cookie_name,
            token,
            max_age=settings.session_ttl_seconds,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="strict",
            path="/",
        )
        return response

    @app.post("/api/auth/logout", status_code=204)
    def logout() -> Response:
        response = Response(status_code=204)
        response.delete_cookie(
            sessions.cookie_name,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="strict",
            path="/",
        )
        return response

    @app.get("/api/session")
    def session_status(request: Request) -> dict[str, str | bool]:
        session = sessions.verify(request.cookies.get(sessions.cookie_name))
        if session is None:
            return {"authenticated": False}
        return {"authenticated": True, "csrf_token": session.csrf_token}

    @app.get("/api/dashboard")
    def dashboard(
        month: str,
        session: Session = Depends(require_session),
    ) -> dict:
        del session
        try:
            return ledger.dashboard(month)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/api/transactions")
    def list_transactions(
        query: str = "",
        account: str = "",
        category: str = "",
        kind: str = "",
        review_state: str = "",
        date_from: str = "",
        date_to: str = "",
        page: int = 1,
        session: Session = Depends(require_session),
    ) -> dict:
        del session
        return ledger.list_transactions(
            {
                "query": query,
                "account": account,
                "category": category,
                "kind": kind,
                "review_state": review_state,
                "date_from": date_from,
                "date_to": date_to,
                "page": page,
            }
        )

    @app.post("/api/transactions", status_code=201)
    def create_transaction(
        body: TransactionBody,
        session: Session = Depends(require_csrf),
    ) -> dict:
        del session
        payload = body.model_dump(mode="json")
        try:
            return ledger.create_manual_transaction(payload, actor="owner")
        except (ValueError, KeyError, sqlite3.IntegrityError) as error:
            raise HTTPException(
                status_code=422,
                detail="记录未保存，请检查账户、分类、金额和时间",
            ) from error

    @app.patch("/api/transactions/{transaction_id}")
    def update_transaction(
        transaction_id: str,
        body: TransactionUpdateBody,
        session: Session = Depends(require_csrf),
    ) -> dict:
        del session
        changes = body.model_dump(exclude_unset=True)
        try:
            return ledger.update_transaction(transaction_id, changes, actor="owner")
        except LookupError as error:
            raise HTTPException(status_code=404, detail="没有找到这笔交易") from error
        except (ValueError, sqlite3.IntegrityError) as error:
            raise HTTPException(
                status_code=422, detail="修改未保存，请检查分类和确认状态"
            ) from error

    @app.get("/api/options")
    def options(
        session: Session = Depends(require_session),
    ) -> dict:
        del session
        return ledger.list_options()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        root = settings.frontend_dist.resolve()
        candidate = (root / path).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        index = root / "index.html"
        if index.is_file():
            return FileResponse(index)
        raise HTTPException(status_code=404, detail="前端资源尚未生成")

    return app
