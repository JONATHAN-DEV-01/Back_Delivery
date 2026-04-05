import os
from flask import Flask
from flask_cors import CORS
from app.extensions import db, migrate
from app.controllers.usuario_controller import users_bp
from app.controllers.auth_controller import auth_bp
from app.controllers.restaurante_controller import restaurante_bp
from app.controllers.produto_controller import produto_bp
from app.controllers.social_auth_controller import social_auth_bp

def create_app():
    app = Flask(__name__)
    
    # Configurar CORS para permitir requisições de um frontend separado
    CORS(app)

    # Configuração do Banco de Dados
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://admin:admin@db:5432/delivery_db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Inicializar as extensões usando o pattern de Application Factory
    db.init_app(app)
    migrate.init_app(app, db)

    # Registrar rotas (Blueprints)
    app.register_blueprint(users_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(restaurante_bp)
    app.register_blueprint(produto_bp)
    app.register_blueprint(social_auth_bp)

    # Importar modelos para que o Alembic/Flask-Migrate os detecte
    from app.models import identidade_social  # noqa: F401

    from flask import send_from_directory
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(os.path.join(app.root_path, '../uploads'), filename)

    return app
