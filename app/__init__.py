import os
from flask import Flask
from flask_cors import CORS
from app.extensions import db, migrate
from app.controllers.usuario_controller import users_bp

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

    return app
