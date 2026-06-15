"""
Postes App - aplicação simples de gestão de projetos de postes.

Dois perfis:
  - admin: cria projetos (via Excel), exporta dados/fotos, gerencia usuários.
  - tecnico: vê projetos por região e preenche observações/fotos no mapa.

Apenas 2 contas (1 admin + 1 técnico), mas várias pessoas podem logar ao
mesmo tempo na mesma conta (Flask-Login permite sessões simultâneas).
"""
import os
import io
import csv
import zipfile
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, jsonify,
    send_file, flash, abort, Response
)
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

REGIOES = ['Sorocaba', 'Jundiai', 'Baixada']
MAX_FOTOS = 3
ALLOWED_PHOTO_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'postes.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32 MB por request

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para continuar.'


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='tecnico')  # admin | tecnico
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        return self.role == 'admin'


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(80), nullable=False)
    regiao = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='aberto')  # aberto | encerrado
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)

    postes = db.relationship('Poste', backref='project', cascade='all, delete-orphan',
                             lazy='dynamic')

    @property
    def total_postes(self):
        return self.postes.count()

    @property
    def preenchidos(self):
        return self.postes.filter(Poste.observacoes.isnot(None),
                                  Poste.observacoes != '').count()


class Poste(db.Model):
    __tablename__ = 'postes'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    observacoes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    photos = db.relationship('Photo', backref='poste', cascade='all, delete-orphan',
                             lazy='dynamic')

    @property
    def preenchido(self):
        return bool(self.observacoes and self.observacoes.strip())

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'observacoes': self.observacoes or '',
            'preenchido': self.preenchido,
            'photos': [{'id': p.id, 'filename': p.filename,
                        'url': url_for('foto_file', poste_id=self.id, filename=p.filename)}
                       for p in self.photos],
        }


class Photo(db.Model):
    __tablename__ = 'photos'
    id = db.Column(db.Integer, primary_key=True)
    poste_id = db.Column(db.Integer, db.ForeignKey('postes.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


def poste_dir(poste_id):
    d = os.path.join(UPLOAD_DIR, f'poste_{poste_id}')
    os.makedirs(d, exist_ok=True)
    return d


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos.', 'error')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    if current_user.is_admin:
        return redirect(url_for('admin_projetos'))
    return redirect(url_for('tecnico_projetos'))


# --------------------------------------------------------------------------
# Técnico
# --------------------------------------------------------------------------
@app.route('/tecnico/projetos')
@login_required
def tecnico_projetos():
    regiao = request.args.get('regiao')
    projetos = []
    if regiao in REGIOES:
        projetos = Project.query.filter_by(regiao=regiao).order_by(Project.numero).all()
    return render_template('tecnico/projetos.html', regioes=REGIOES,
                           regiao_sel=regiao, projetos=projetos)


@app.route('/tecnico/mapa')
@app.route('/tecnico/mapa/<int:project_id>')
@login_required
def tecnico_mapa(project_id=None):
    projeto = db.session.get(Project, project_id) if project_id else None
    return render_template('tecnico/mapa.html', projeto=projeto)


# --------------------------------------------------------------------------
# API (mapa)
# --------------------------------------------------------------------------
@app.route('/api/projeto/<int:project_id>')
@login_required
def api_projeto(project_id):
    p = db.session.get(Project, project_id) or abort(404)
    postes = [pt.to_dict() for pt in p.postes.order_by(Poste.id)]
    return jsonify({
        'id': p.id, 'numero': p.numero, 'regiao': p.regiao,
        'status': p.status, 'postes': postes,
        'can_edit': True,
    })


@app.route('/api/poste/<int:poste_id>', methods=['POST'])
@login_required
def api_poste_update(poste_id):
    pt = db.session.get(Poste, poste_id) or abort(404)
    data = request.get_json(silent=True) or {}
    pt.observacoes = (data.get('observacoes') or '').strip()
    db.session.commit()
    return jsonify(pt.to_dict())


@app.route('/api/poste/<int:poste_id>/foto', methods=['POST'])
@login_required
def api_poste_foto(poste_id):
    pt = db.session.get(Poste, poste_id) or abort(404)
    if pt.photos.count() >= MAX_FOTOS:
        return jsonify({'error': f'Máximo de {MAX_FOTOS} fotos por ponto.'}), 400
    file = request.files.get('foto')
    if not file or not file.filename:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_PHOTO_EXT:
        return jsonify({'error': 'Formato de imagem não suportado.'}), 400
    stamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    fname = secure_filename(f'p{poste_id}_{stamp}{ext}')
    file.save(os.path.join(poste_dir(poste_id), fname))
    photo = Photo(poste_id=poste_id, filename=fname)
    db.session.add(photo)
    db.session.commit()
    return jsonify(pt.to_dict())


@app.route('/api/poste/<int:poste_id>/foto/<int:photo_id>', methods=['DELETE'])
@login_required
def api_poste_foto_delete(poste_id, photo_id):
    photo = db.session.get(Photo, photo_id) or abort(404)
    if photo.poste_id != poste_id:
        abort(404)
    try:
        os.remove(os.path.join(poste_dir(poste_id), photo.filename))
    except OSError:
        pass
    db.session.delete(photo)
    db.session.commit()
    pt = db.session.get(Poste, poste_id)
    return jsonify(pt.to_dict())


@app.route('/api/projeto/<int:project_id>/status', methods=['POST'])
@login_required
def api_projeto_status(project_id):
    p = db.session.get(Project, project_id) or abort(404)
    data = request.get_json(silent=True) or {}
    novo = data.get('status')
    if novo not in ('aberto', 'encerrado'):
        return jsonify({'error': 'Status inválido.'}), 400
    p.status = novo
    p.closed_at = datetime.utcnow() if novo == 'encerrado' else None
    db.session.commit()
    return jsonify({'status': p.status})


@app.route('/uploads/poste_<int:poste_id>/<path:filename>')
@login_required
def foto_file(poste_id, filename):
    return send_file(os.path.join(poste_dir(poste_id), secure_filename(filename)))


# --------------------------------------------------------------------------
# Admin - Projetos (import Excel)
# --------------------------------------------------------------------------
@app.route('/admin/projetos', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_projetos():
    if request.method == 'POST':
        file = request.files.get('arquivo')
        if not file or not file.filename:
            flash('Selecione um arquivo Excel (.xlsx).', 'error')
            return redirect(url_for('admin_projetos'))
        try:
            criados, postes_count = importar_excel(file)
            flash(f'{criados} projeto(s) criado(s) com {postes_count} ponto(s).', 'success')
        except Exception as e:
            flash(f'Erro ao processar o arquivo: {e}', 'error')
        return redirect(url_for('admin_projetos'))
    projetos = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('admin/projetos.html', projetos=projetos)


@app.route('/admin/projeto/<int:project_id>/excluir', methods=['POST'])
@login_required
@admin_required
def admin_projeto_excluir(project_id):
    p = db.session.get(Project, project_id) or abort(404)
    for pt in p.postes:
        d = os.path.join(UPLOAD_DIR, f'poste_{pt.id}')
        if os.path.isdir(d):
            for f in os.listdir(d):
                try:
                    os.remove(os.path.join(d, f))
                except OSError:
                    pass
    db.session.delete(p)
    db.session.commit()
    flash('Projeto excluído.', 'success')
    return redirect(url_for('admin_projetos'))


def importar_excel(file):
    import openpyxl
    wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError('Planilha vazia.')

    header = [str(c).strip().lower() if c is not None else '' for c in rows[0]]

    def find_col(*names):
        for n in names:
            for i, h in enumerate(header):
                if n in h:
                    return i
        return None

    col_num = find_col('número do projeto', 'numero do projeto', 'projeto', 'número', 'numero')
    col_lat = find_col('latitude', 'lat')
    col_lng = find_col('longitude', 'long', 'lng', 'lon')
    col_reg = find_col('região', 'regiao', 'region')

    if None in (col_num, col_lat, col_lng, col_reg):
        raise ValueError('Colunas esperadas: Número do projeto, Latitude, Longitude, Região.')

    grupos = {}  # numero -> {'regiao': str, 'postes': [(lat,lng)]}
    for row in rows[1:]:
        if row is None:
            continue
        numero = row[col_num]
        lat = row[col_lat]
        lng = row[col_lng]
        regiao = row[col_reg]
        if numero is None or lat is None or lng is None:
            continue
        numero = str(numero).strip()
        regiao = str(regiao).strip() if regiao is not None else ''
        try:
            lat = float(str(lat).replace(',', '.'))
            lng = float(str(lng).replace(',', '.'))
        except ValueError:
            continue
        g = grupos.setdefault(numero, {'regiao': regiao, 'postes': []})
        if not g['regiao'] and regiao:
            g['regiao'] = regiao
        g['postes'].append((lat, lng))

    criados = 0
    postes_count = 0
    for numero, info in grupos.items():
        regiao = info['regiao'] or 'Sem região'
        # normaliza para uma das regiões conhecidas, se possível
        for r in REGIOES:
            if r.lower() in regiao.lower():
                regiao = r
                break
        projeto = Project(numero=numero, regiao=regiao, status='aberto')
        db.session.add(projeto)
        db.session.flush()
        for lat, lng in info['postes']:
            db.session.add(Poste(project_id=projeto.id, latitude=lat, longitude=lng))
            postes_count += 1
        criados += 1
    db.session.commit()
    return criados, postes_count


# --------------------------------------------------------------------------
# Admin - Dados (tabela + exports)
# --------------------------------------------------------------------------
@app.route('/admin/dados')
@login_required
@admin_required
def admin_dados():
    linhas = []
    projetos = Project.query.order_by(Project.numero).all()
    for p in projetos:
        for pt in p.postes.order_by(Poste.id):
            linhas.append({
                'numero': p.numero,
                'regiao': p.regiao,
                'status': p.status,
                'latitude': pt.latitude,
                'longitude': pt.longitude,
                'observacoes': pt.observacoes or '',
                'fotos': ', '.join(ph.filename for ph in pt.photos),
            })
    return render_template('admin/dados.html', linhas=linhas, projetos=projetos)


@app.route('/admin/dados/export.csv')
@login_required
@admin_required
def admin_export_csv():
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['Número do projeto', 'Região', 'Status', 'Latitude',
                     'Longitude', 'Observações', 'Fotos'])
    for p in Project.query.order_by(Project.numero).all():
        for pt in p.postes.order_by(Poste.id):
            writer.writerow([p.numero, p.regiao, p.status, pt.latitude,
                             pt.longitude, pt.observacoes or '',
                             ', '.join(ph.filename for ph in pt.photos)])
    data = output.getvalue().encode('utf-8-sig')
    return Response(
        data, mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=dados_projetos.csv'})


@app.route('/admin/dados/fotos.zip')
@login_required
@admin_required
def admin_export_fotos():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in Project.query.all():
            for pt in p.postes:
                for ph in pt.photos:
                    path = os.path.join(UPLOAD_DIR, f'poste_{pt.id}', ph.filename)
                    if os.path.exists(path):
                        arc = f'{p.numero}/poste_{pt.id}/{ph.filename}'
                        zf.write(path, arc)
    mem.seek(0)
    return send_file(mem, mimetype='application/zip', as_attachment=True,
                     download_name='fotos_projetos.zip')


# --------------------------------------------------------------------------
# Admin - Usuários
# --------------------------------------------------------------------------
@app.route('/admin/usuarios', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_usuarios():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'create':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            role = request.form.get('role', 'tecnico')
            if not username or not password:
                flash('Usuário e senha são obrigatórios.', 'error')
            elif User.query.filter_by(username=username).first():
                flash('Já existe um usuário com esse nome.', 'error')
            else:
                u = User(username=username, role=role)
                u.set_password(password)
                db.session.add(u)
                db.session.commit()
                flash('Usuário criado.', 'success')
        elif action == 'update':
            uid = request.form.get('user_id')
            u = db.session.get(User, int(uid)) if uid else None
            if u:
                new_username = request.form.get('username', '').strip()
                new_role = request.form.get('role', u.role)
                new_password = request.form.get('password', '')
                if new_username:
                    u.username = new_username
                u.role = new_role
                if new_password:
                    u.set_password(new_password)
                db.session.commit()
                flash('Usuário atualizado.', 'success')
        elif action == 'delete':
            uid = request.form.get('user_id')
            u = db.session.get(User, int(uid)) if uid else None
            if u and u.id != current_user.id:
                db.session.delete(u)
                db.session.commit()
                flash('Usuário removido.', 'success')
            else:
                flash('Não é possível remover o próprio usuário.', 'error')
        return redirect(url_for('admin_usuarios'))
    usuarios = User.query.order_by(User.role, User.username).all()
    return render_template('admin/usuarios.html', usuarios=usuarios)


# --------------------------------------------------------------------------
# CLI / seed
# --------------------------------------------------------------------------
def seed():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        u = User(username='admin', role='admin')
        u.set_password('admin123')
        db.session.add(u)
    if not User.query.filter_by(username='tecnico').first():
        u = User(username='tecnico', role='tecnico')
        u.set_password('tecnico123')
        db.session.add(u)
    db.session.commit()
    print('Banco inicializado. Usuários: admin/admin123 e tecnico/tecnico123')


@app.cli.command('seed')
def seed_cmd():
    seed()


with app.app_context():
    seed()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
