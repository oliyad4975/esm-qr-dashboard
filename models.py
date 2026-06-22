from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# Import db from app - same instance!
from app import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    capas = db.relationship('CAPA', backref='owner_user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class CAPA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    capa_id = db.Column(db.String(20), unique=True, nullable=False)
    source = db.Column(db.String(50))
    description = db.Column(db.Text)
    root_cause = db.Column(db.Text)
    action_type = db.Column(db.String(20))
    owner = db.Column(db.String(100))
    due_date = db.Column(db.Date)
    action_taken = db.Column(db.Text)
    progress_status = db.Column(db.String(50), default='Not Started')
    status = db.Column(db.String(50), default='Open')
    date_opened = db.Column(db.DateTime, default=datetime.utcnow)
    date_closed = db.Column(db.DateTime)
    action_started_date = db.Column(db.Date)
    action_completed_date = db.Column(db.Date)
    effectiveness_check = db.Column(db.Text)
    feedback = db.Column(db.Text)
    verified_by = db.Column(db.String(100))
    verification_date = db.Column(db.Date)
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Relationship for evidence files
    evidence_files = db.relationship('EvidenceFile', backref='capa', lazy=True, cascade='all, delete-orphan')
    
    def is_overdue(self):
        if self.due_date and self.status not in ['Closed', 'Completed']:
            return self.due_date < datetime.utcnow().date()
        return False

class EvidenceFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(100))
    description = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_by = db.Column(db.String(100))
    
    capa_id = db.Column(db.Integer, db.ForeignKey('capa.id'), nullable=False)

class OrganizationSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_logo = db.Column(db.String(255))
    company_name = db.Column(db.String(100))
    document_title = db.Column(db.String(100), default='CAPA Report')
    document_number = db.Column(db.String(100))
    department = db.Column(db.String(100))
    process_owner = db.Column(db.String(100))
    address_line1 = db.Column(db.String(200))
    address_line2 = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))

    @staticmethod
    def get_settings():
        settings = OrganizationSettings.query.first()
        if not settings:
            settings = OrganizationSettings()
            db.session.add(settings)
            db.session.commit()
        return settings