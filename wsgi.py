"""
WSGI de produção para PythonAnywhere.

No painel "Web" do PythonAnywhere, edite o arquivo WSGI
(ex.: /var/www/gridmapgovernance_pythonanywhere_com_wsgi.py)
e deixe-o com o conteúdo abaixo (ou faça ele importar este módulo).
"""
import os
import sys

# Caminho do projeto no PythonAnywhere (ajuste o usuário se necessário)
project_home = os.environ.get(
    'PROJECT_HOME',
    '/home/gridmapgovernance/PostesApp'
)
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Chave secreta de produção — troque por um valor próprio no painel "Web" > Environment,
# ou edite a linha abaixo.
os.environ.setdefault('SECRET_KEY', 'troque-esta-chave-em-producao')

from app import app as application  # noqa: E402
