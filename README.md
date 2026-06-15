# Postes App

Aplicação simples de gestão de projetos de postes com 2 perfis: **admin** e **técnico**.

## Como rodar

```powershell
pip install -r requirements.txt
python app.py
```

Acesse http://localhost:5000

## Contas padrão (criadas automaticamente)

- **Admin:** `admin` / `admin123`
- **Técnico:** `tecnico` / `tecnico123`

Várias pessoas podem logar ao mesmo tempo na mesma conta.

## Perfil Técnico

- **Projetos:** notas agrupadas por região (Sorocaba, Jundiaí, Baixada).
- **Mapa:** MapLibre com 2 tiles (OSM e Branco) e postes (pontos verdes).
  - Clicar no ponto abre um modal: **Editar** (barra lateral esquerda com
    observações + até 3 fotos) ou **Ver no mapa** (abre rota no Google Maps).
  - O projeto pode ser **encerrado** e depois **reaberto/alterado**.

## Perfil Admin

- **Projetos:** importa Excel (.xlsx) com colunas: `Número do projeto`,
  `Latitude`, `Longitude`, `Região`. Linhas com o mesmo número viram um único
  projeto; os pontos são criados no mapa automaticamente.
- **Dados:** tabela com todos os pontos; download em CSV e download das fotos (.zip).
- **Usuários:** criar/editar/remover contas.

## Mapa

- 2 tiles: **OSM** e **Branco** (CARTO light).
- **Localização do usuário**: botão de geolocalização (canto inferior direito).
- **Busca de endereço**: campo no canto superior esquerdo (Nominatim/OpenStreetMap).

## Estrutura

```
app.py                # backend (Flask + SQLAlchemy + Flask-Login)
wsgi.py               # entrada WSGI para produção (PythonAnywhere)
templates/            # páginas (Jinja + Tailwind CDN)
static/js/mapa.js     # mapa do técnico (MapLibre + geocoder + geolocate)
static/img/logo.png   # logo Grid Map Atlas
uploads/              # fotos enviadas
postes.db             # banco SQLite (criado automaticamente)
```

## Deploy no PythonAnywhere

Conta: `gridmapgovernance` (https://www.pythonanywhere.com/user/gridmapgovernance/)

1. **Enviar o código.** No console Bash do PythonAnywhere, envie a pasta
   `PostesApp` para `/home/gridmapgovernance/PostesApp` (via `git clone` do seu
   repositório ou pelo upload de arquivos do painel "Files").

2. **Criar o virtualenv e instalar dependências:**
   ```bash
   cd ~/PostesApp
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Criar o Web App.** Painel **Web → Add a new web app → Manual configuration**
   (escolha o mesmo Python do virtualenv, ex.: Python 3.11).

4. **Virtualenv.** Em "Virtualenv", informe:
   `/home/gridmapgovernance/PostesApp/.venv`

5. **WSGI.** Em "WSGI configuration file", abra o arquivo e substitua todo o
   conteúdo por:
   ```python
   import sys, os
   project_home = '/home/gridmapgovernance/PostesApp'
   if project_home not in sys.path:
       sys.path.insert(0, project_home)
   os.environ.setdefault('SECRET_KEY', 'coloque-uma-chave-secreta-forte')
   from app import app as application
   ```

6. **Static files (opcional, recomendado).** Em "Static files":
   - URL: `/static/`  →  Directory: `/home/gridmapgovernance/PostesApp/static/`

7. **Reload.** Clique em **Reload** no painel "Web".

8. **Primeiro acesso.** Ao abrir o site, o banco `postes.db` e os usuários
   padrão (`admin`/`admin123` e `tecnico`/`tecnico123`) são criados
   automaticamente. Depois é só entrar como admin e criar/alterar os usuários
   definitivos na aba **Usuários**.

> Os tiles do mapa, a busca de endereço e a localização do usuário rodam no
> navegador, então funcionam normalmente mesmo na conta gratuita (que restringe
> apenas requisições externas feitas pelo servidor).
