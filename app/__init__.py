from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from config import Config
import os

db = SQLAlchemy()
bcrypt = Bcrypt()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Init extensions
    db.init_app(app)
    bcrypt.init_app(app)
    
    CORS(app, resources={r"/api/*": {"origins": "*"}})  # Allow any origin to access the API

    migrate.init_app(app, db)

    # Register Blueprints
    from app.routes.auth_routes import auth_bp
    from app.routes.profile_routes import profile_bp
    from app.routes.user_routes import user_routes
    from app.routes.detection_route import detection_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(profile_bp, url_prefix='/api/profile')
    app.register_blueprint(user_routes, url_prefix='/api/user')
    app.register_blueprint(detection_bp, url_prefix='/api/detect')

    return app
