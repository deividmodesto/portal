def application(environ, start_response):
    """Um simples 'Olá Mundo' WSGI."""
    status = '200 OK'
    headers = [('Content-type', 'text/plain; charset=utf-8')]
    start_response(status, headers)
    return [b"Ola Mundo! A ligacao IIS -> Python funciona!"]