"""Pytest para exception handlers — migrado de smoke_servidor_exception_handlers."""
import inspect

import pytest

fastapi = pytest.importorskip("fastapi")
TestClient = pytest.importorskip("fastapi.testclient").TestClient


class _ErrorDePrueba(Exception):
    pass


def _app_rota():
    from fastapi import FastAPI, HTTPException as FastAPIHTTPException
    app_roto = FastAPI()

    @app_roto.exception_handler(_ErrorDePrueba)
    async def _handler_roto(request, exc):
        return FastAPIHTTPException(status_code=422, detail=str(exc))

    @app_roto.get("/falla")
    def _falla():
        raise _ErrorDePrueba("mensaje de prueba")

    return app_roto


def _app_correcta():
    from fastapi import FastAPI
    from starlette.responses import JSONResponse
    app_bien = FastAPI()

    @app_bien.exception_handler(_ErrorDePrueba)
    async def _handler_bien(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app_bien.get("/falla")
    def _falla2():
        raise _ErrorDePrueba("mensaje de prueba")

    return app_bien


def test_patron_roto_da_500():
    r = TestClient(_app_rota(), raise_server_exceptions=False).get("/falla")
    assert r.status_code == 500


def test_patron_correcto_da_422():
    r = TestClient(_app_correcta()).get("/falla")
    assert r.status_code == 422
    assert r.json()["detail"] == "mensaje de prueba"


def test_handlers_reales_usan_jsonresponse():
    import server.servidor as srv
    for nombre_handler in ("validation_error_handler", "repository_error_handler",
                           "data_service_error_handler"):
        src = inspect.getsource(getattr(srv, nombre_handler))
        assert "JSONResponse" in src
        assert "return HTTPException" not in src
