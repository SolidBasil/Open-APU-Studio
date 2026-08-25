"""
smoke_servidor_exception_handlers.py
======================================
Prueba de humo del fix a los exception_handler globales de
server/servidor.py: devolvían `HTTPException(...)` en vez de un
`Response` real (`JSONResponse`). Un exception_handler de FastAPI/
Starlette DEBE devolver un objeto Response de verdad — HTTPException es
solo un vehículo para levantar un error dentro de un endpoint, no algo
que el framework sepa enviar como respuesta. El resultado, antes del
fix: cualquier endpoint SIN su propio try/except que dependiera del
manejador global crasheaba con
`TypeError: 'HTTPException' object is not callable` en cuanto se
disparaba un ValidationError/RepositoryError/DataServiceError — el
cliente recibía un error de conexión roto, no el 422/500 con mensaje
claro que se pretendía.

Encontrado en la pasada de verificación final de la migración a HTTP,
probando el mecanismo de forma aislada (no era alcanzable por los tests
de paridad porque los endpoints que sí escriben datos, en su mayoría,
ya tienen su propio try/except local que enmascaraba el problema).

No es un bug introducido por la sesión — los tres handlers ya existían
antes; se corrigieron los tres al mismo tiempo.

Uso:
    python3 tests/smoke_servidor_exception_handlers.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    # ── Caso 1: reproducir el bug de forma aislada (HTTPException) ──────
    from fastapi import FastAPI, HTTPException as FastAPIHTTPException
    from fastapi.testclient import TestClient

    class _ErrorDePrueba(Exception):
        pass

    app_roto = FastAPI()

    @app_roto.exception_handler(_ErrorDePrueba)
    async def _handler_roto(request, exc):
        return FastAPIHTTPException(status_code=422, detail=str(exc))  # el bug

    @app_roto.get("/falla")
    def _falla():
        raise _ErrorDePrueba("mensaje de prueba")

    client_roto = TestClient(app_roto, raise_server_exceptions=False)
    r_roto = client_roto.get("/falla")
    assert r_roto.status_code == 500, (
        f"se esperaba que el patrón roto (return HTTPException) diera 500 "
        f"con detalle perdido, dio {r_roto.status_code}: {r_roto.text}"
    )
    print(f"OK: reproducido el bug de forma aislada — 'return HTTPException(...)' "
          f"en un exception_handler da {r_roto.status_code} en vez de 422, "
          f"con el mensaje real perdido")

    # ── Caso 2: el patrón correcto (JSONResponse) ────────────────────────
    from starlette.responses import JSONResponse

    app_bien = FastAPI()

    @app_bien.exception_handler(_ErrorDePrueba)
    async def _handler_bien(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app_bien.get("/falla")
    def _falla2():
        raise _ErrorDePrueba("mensaje de prueba")

    client_bien = TestClient(app_bien)
    r_bien = client_bien.get("/falla")
    assert r_bien.status_code == 422
    assert r_bien.json()["detail"] == "mensaje de prueba"
    print("OK: el patrón correcto (JSONResponse) da 422 con el mensaje real intacto")

    # ── Caso 3: los 3 handlers reales de server/servidor.py usan el patrón correcto ──
    import inspect
    import server.servidor as srv

    for nombre_handler in ("validation_error_handler", "repository_error_handler",
                           "data_service_error_handler"):
        fn = getattr(srv, nombre_handler)
        src = inspect.getsource(fn)
        assert "JSONResponse" in src, (
            f"{nombre_handler} debía usar JSONResponse, código fuente:\n{src}"
        )
        assert "return HTTPException" not in src, (
            f"{nombre_handler} todavía tiene el patrón roto 'return HTTPException'"
        )
    print("OK: los 3 exception_handler reales del servidor (ValidationError, "
          "RepositoryError, DataServiceError) usan el patrón correcto")

    print("\nTODAS LAS PRUEBAS DEL FIX DE EXCEPTION HANDLERS PASARON")


if __name__ == "__main__":
    main()
