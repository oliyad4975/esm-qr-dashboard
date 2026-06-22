import os
import smtplib
import uuid
import shutil
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itsdangerous import URLSafeTimedSerializer
from flask import render_template, redirect, url_for, flash, request, make_response, send_from_directory
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from weasyprint import HTML
from datetime import datetime
from werkzeug.utils import secure_filename
from models import db, CAPA, OrganizationSettings, User, EvidenceFile
from forms import (
    CAPAForm,
    CAPAUpdateForm,
    CAPACloseForm,
    OrganizationSettingsForm,
    LoginForm,
    RegistrationForm,
    EvidenceUploadForm,
    RequestResetForm,
    ResetPasswordForm,
)
from app import app

# ==================== HELPER FUNCTIONS ====================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def is_mail_configured():
    username = app.config.get('MAIL_USERNAME', '')
    password = app.config.get('MAIL_PASSWORD', '')
    placeholder_values = {'your-email@example.com', 'your-email-password', ''}
    return username not in placeholder_values and password not in placeholder_values


def save_evidence_file(file, capa_id):
    """Save uploaded evidence file and return file info"""
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        file_ext = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"CAPA_{capa_id}_{uuid.uuid4().hex[:8]}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{file_ext}"
        
        capa_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'capa_{capa_id}')
        os.makedirs(capa_upload_dir, exist_ok=True)
        
        file_path = os.path.join(capa_upload_dir, unique_filename)
        file.save(file_path)
        
        return {
            'filename': unique_filename,
            'original_filename': original_filename,
            'file_path': file_path,
            'file_size': os.path.getsize(file_path),
            'file_type': file_ext
        }
    return None

# ==================== PUBLIC ROUTES ====================

@app.route('/')
def home():
    """Root route - landing page for guests, dashboard for logged-in users"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('landing.html')

# ==================== AUTH ROUTES ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        # Check if username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already taken. Please choose another.', 'error')
            return render_template('register.html', form=form)
        
        # Check if email already exists
        existing_email = User.query.filter_by(email=form.email.data).first()
        if existing_email:
            flash('Email already registered. Please use another or login.', 'error')
            return render_template('register.html', form=form)
        
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
            token = serializer.dumps(user.email, salt='password-reset-salt')
            reset_url = url_for('reset_token', token=token, _external=True)

            if is_mail_configured():
                try:
                    send_reset_email(user.email, reset_url)
                    flash('A password reset link has been sent to your email.', 'success')
                except Exception as e:
                    app.logger.exception('Failed to send password reset email')
                    app.logger.info('Password reset URL (development fallback): %s', reset_url)
                    flash('Email sending failed. The reset link was written to the server log for development.', 'warning')
            else:
                app.logger.info('Password reset URL (development fallback): %s', reset_url)
                flash('Password reset email is not configured. The reset link was written to the server log for development.', 'warning')
        else:
            flash('If an account with that email exists, a password reset link has been sent.', 'info')

        return redirect(url_for('login'))

    return render_template('reset_request.html', title='Reset Password', form=form)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    try:
        serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash('The reset link is invalid or has expired.', 'error')
        return redirect(url_for('reset_request'))

    user = User.query.filter_by(email=email).first_or_404()
    form = ResetPasswordForm()

    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_token.html', token=token, form=form)

def send_reset_email(to_email, reset_url):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Password Reset Request - CAPA Dashboard'
    msg['From'] = app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = to_email
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #667eea;">Password Reset Request</h2>
            <p>You requested a password reset for your CAPA Dashboard account.</p>
            <p>Click the button below to reset your password:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="word-break: break-all; background: #f5f5f5; padding: 10px; border-radius: 5px;">{reset_url}</p>
            <p><strong>This link expires in 1 hour.</strong></p>
            <p style="color: #666; font-size: 14px;">If you didn't request this password reset, please ignore this email. Your account remains secure.</p>
        </div>
    </body>
    </html>
    """
    
    msg.attach(MIMEText(html, 'html'))
    
    with smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT']) as server:
        server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    total_capas = CAPA.query.count()
    return render_template('admin_dashboard.html', users=users, total_capas=total_capas)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/user/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('You cannot delete your own admin account.', 'error')
        return redirect(url_for('admin_users'))
    
    capas = CAPA.query.filter_by(user_id=user.id).all()
    for capa in capas:
        for evidence in capa.evidence_files:
            if os.path.exists(evidence.file_path):
                os.remove(evidence.file_path)
        capa_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'capa_{capa.id}')
        if os.path.exists(capa_dir):
            shutil.rmtree(capa_dir)
    
    CAPA.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} and all their CAPAs deleted.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/user/<int:id>/toggle_admin', methods=['POST'])
@login_required
@admin_required
def admin_toggle_admin(id):
    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash('You cannot remove your own admin status.', 'error')
        return redirect(url_for('admin_users'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    status = "granted" if user.is_admin else "removed"
    flash(f'Admin access {status} for {user.username}.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/capas')
@login_required
@admin_required
def admin_capas():
    capas = CAPA.query.order_by(CAPA.date_opened.desc()).all()
    return render_template('admin_capas.html', capas=capas)

@app.route('/admin/capa/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_capa(id):
    capa = CAPA.query.get_or_404(id)
    
    for evidence in capa.evidence_files:
        if os.path.exists(evidence.file_path):
            os.remove(evidence.file_path)
    capa_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'capa_{capa.id}')
    if os.path.exists(capa_dir):
        shutil.rmtree(capa_dir)
    
    db.session.delete(capa)
    db.session.commit()
    flash(f'CAPA {capa.capa_id} deleted.', 'success')
    return redirect(url_for('admin_capas'))

# ==================== MAIN ROUTES ====================

@app.route('/dashboard')
@login_required
def index():
    total = CAPA.query.filter_by(user_id=current_user.id).count()
    open_count = CAPA.query.filter_by(user_id=current_user.id, status='Open').count()
    in_progress = CAPA.query.filter_by(user_id=current_user.id, status='In Progress').count()
    pending = CAPA.query.filter_by(user_id=current_user.id, status='Pending Verification').count()
    overdue_count = CAPA.query.filter(CAPA.user_id == current_user.id,
                                      CAPA.due_date < datetime.utcnow().date(),
                                      CAPA.status.notin_(['Closed', 'Completed'])).count()
    recent = CAPA.query.filter_by(user_id=current_user.id).order_by(CAPA.date_opened.desc()).limit(5).all()
    return render_template('index.html', total=total, open=open_count,
                          in_progress=in_progress, pending=pending,
                          overdue=overdue_count, recent=recent)

@app.route('/capas')
@login_required
def capa_list():
    status_filter = request.args.get('status', 'all')
    if status_filter == 'all':
        capas = CAPA.query.filter_by(user_id=current_user.id).order_by(CAPA.date_opened.desc()).all()
    else:
        capas = CAPA.query.filter_by(user_id=current_user.id, status=status_filter).order_by(CAPA.date_opened.desc()).all()
    return render_template('capa_list.html', capas=capas, current_filter=status_filter)

@app.route('/capa/new', methods=['GET', 'POST'])
@login_required
def capa_new():
    form = CAPAForm()
    if form.validate_on_submit():
        new_capa = CAPA(
            capa_id=f"CAPA-{datetime.utcnow().year}-{uuid.uuid4().hex[:8].upper()}",
            source=form.source.data,
            description=form.description.data,
            root_cause=form.root_cause.data,
            action_type=form.action_type.data,
            owner=form.owner.data,
            due_date=form.due_date.data,
            action_taken=form.action_taken.data,
            progress_status='Not Started',
            status='Open',
            user_id=current_user.id
        )
        db.session.add(new_capa)
        db.session.commit()
        flash('CAPA created successfully!', 'success')
        return redirect(url_for('capa_detail', id=new_capa.id))
    return render_template('capa_new.html', form=form)

@app.route('/capa/<int:id>')
@login_required
def capa_detail(id):
    capa = CAPA.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    evidence_files = EvidenceFile.query.filter_by(capa_id=capa.id).order_by(EvidenceFile.uploaded_at.desc()).all()
    return render_template('capa_detail.html', capa=capa, evidence_files=evidence_files)

@app.route('/capa/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def capa_edit(id):
    capa = CAPA.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = CAPAUpdateForm(obj=capa)
    if form.validate_on_submit():
        capa.progress_status = form.progress_status.data
        capa.action_taken = form.action_taken.data
        capa.root_cause = form.root_cause.data
        capa.action_started_date = form.action_started_date.data
        capa.action_completed_date = form.action_completed_date.data
        capa.effectiveness_check = form.effectiveness_check.data
        capa.feedback = form.feedback.data
        capa.verified_by = form.verified_by.data
        capa.verification_date = form.verification_date.data
        capa.status = form.status.data
        
        if capa.progress_status == 'Action Started' and not capa.action_started_date:
            capa.action_started_date = datetime.utcnow()
        if capa.progress_status == 'Completed' and not capa.action_completed_date:
            capa.action_completed_date = datetime.utcnow()
        
        db.session.commit()
        flash('CAPA updated successfully!', 'success')
        return redirect(url_for('capa_detail', id=capa.id))
    return render_template('capa_edit.html', form=form, capa=capa)

@app.route('/capa/<int:id>/close', methods=['GET', 'POST'])
@login_required
def capa_close(id):
    capa = CAPA.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = CAPACloseForm()
    if form.validate_on_submit():
        capa.effectiveness_check = form.effectiveness_check.data
        capa.feedback = form.feedback.data
        capa.verified_by = form.verified_by.data
        capa.verification_date = form.verification_date.data
        capa.status = 'Closed'
        capa.date_closed = datetime.utcnow()
        capa.progress_status = 'Completed'
        db.session.commit()
        flash('CAPA closed successfully!', 'success')
        return redirect(url_for('capa_detail', id=capa.id))
    return render_template('capa_close.html', form=form, capa=capa)

@app.route('/capa/<int:id>/delete', methods=['POST'])
@login_required
def capa_delete(id):
    capa = CAPA.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    for evidence in capa.evidence_files:
        if os.path.exists(evidence.file_path):
            os.remove(evidence.file_path)
    capa_dir = os.path.join(app.config['UPLOAD_FOLDER'], f'capa_{capa.id}')
    if os.path.exists(capa_dir):
        shutil.rmtree(capa_dir)
    
    db.session.delete(capa)
    db.session.commit()
    flash('CAPA deleted successfully!', 'success')
    return redirect(url_for('capa_list'))

# ==================== EVIDENCE ROUTES ====================

@app.route('/capa/<int:id>/evidence/upload', methods=['GET', 'POST'])
@login_required
def upload_evidence(id):
    capa = CAPA.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = EvidenceUploadForm()
    
    if form.validate_on_submit():
        file = form.evidence_file.data
        file_info = save_evidence_file(file, capa.id)
        
        if file_info:
            evidence = EvidenceFile(
                filename=file_info['filename'],
                original_filename=file_info['original_filename'],
                file_path=file_info['file_path'],
                file_size=file_info['file_size'],
                file_type=file_info['file_type'],
                description=form.description.data,
                uploaded_by=current_user.username,
                capa_id=capa.id
            )
            db.session.add(evidence)
            db.session.commit()
            flash('Evidence uploaded successfully!', 'success')
        else:
            flash('Invalid file type or upload failed.', 'error')
        
        return redirect(url_for('capa_detail', id=capa.id))
    
    return render_template('upload_evidence.html', form=form, capa=capa)

@app.route('/evidence/<int:evidence_id>/download')
@login_required
def download_evidence(evidence_id):
    evidence = EvidenceFile.query.get_or_404(evidence_id)
    capa = CAPA.query.get_or_404(evidence.capa_id)
    
    if capa.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if not os.path.exists(evidence.file_path):
        flash('File not found.', 'error')
        return redirect(url_for('capa_detail', id=capa.id))
    
    directory = os.path.dirname(evidence.file_path)
    filename = os.path.basename(evidence.file_path)
    
    return send_from_directory(directory, filename, as_attachment=True, 
                               download_name=evidence.original_filename)

@app.route('/evidence/<int:evidence_id>/delete', methods=['POST'])
@login_required
def delete_evidence(evidence_id):
    evidence = EvidenceFile.query.get_or_404(evidence_id)
    capa = CAPA.query.get_or_404(evidence.capa_id)
    
    if capa.user_id != current_user.id and not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    if os.path.exists(evidence.file_path):
        os.remove(evidence.file_path)
    
    db.session.delete(evidence)
    db.session.commit()
    flash('Evidence deleted successfully!', 'success')
    return redirect(url_for('capa_detail', id=capa.id))

# ==================== SETTINGS ROUTE ====================

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    org_settings = OrganizationSettings.get_settings()
    form = OrganizationSettingsForm(obj=org_settings)
    
    if form.validate_on_submit():
        if form.company_logo.data:
            logo = form.company_logo.data
            filename = secure_filename(logo.filename)
            logo_dir = os.path.join(app.static_folder, 'uploads', 'logos')
            os.makedirs(logo_dir, exist_ok=True)
            logo_path = os.path.join(logo_dir, filename)
            logo.save(logo_path)
            org_settings.company_logo = os.path.join('uploads', 'logos', filename).replace('\\', '/')
        org_settings.company_name = form.company_name.data
        org_settings.document_title = form.document_title.data
        org_settings.document_number = form.document_number.data
        org_settings.department = form.department.data
        org_settings.process_owner = form.process_owner.data
        org_settings.email = form.email.data
        db.session.commit()
        flash('Settings saved successfully!', 'success')
        return redirect(url_for('index'))
    elif request.method == 'POST':
        flash('Please correct the highlighted errors and try again.', 'error')
    
    return render_template('settings.html', form=form, org_settings=org_settings)

# ==================== PDF REPORT ROUTES ====================

@app.route('/capa/<int:id>/pdf')
@login_required
def capa_pdf(id):
    capa = CAPA.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    settings = OrganizationSettings.get_settings()
    evidence_files = EvidenceFile.query.filter_by(capa_id=capa.id).order_by(EvidenceFile.uploaded_at.desc()).all()
    
    html_string = render_template('capa_pdf.html', 
                                  capa=capa, 
                                  settings=settings,
                                  evidence_files=evidence_files,
                                  now=datetime.utcnow())
    
    html = HTML(string=html_string, base_url=request.url_root)
    pdf = html.write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={capa.capa_id}.pdf'
    
    return response

@app.route('/capas/pdf')
@login_required
def capas_list_pdf():
    capas = CAPA.query.filter_by(user_id=current_user.id).order_by(CAPA.date_opened.desc()).all()
    settings = OrganizationSettings.get_settings()
    
    capa_evidence_counts = {}
    for capa in capas:
        capa_evidence_counts[capa.id] = EvidenceFile.query.filter_by(capa_id=capa.id).count()
    
    html_string = render_template('capas_list_pdf.html', 
                                  capas=capas, 
                                  settings=settings,
                                  capa_evidence_counts=capa_evidence_counts,
                                  now=datetime.utcnow())
    
    html = HTML(string=html_string, base_url=request.url_root)
    pdf = html.write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=CAPA_Report.pdf'
    
    return response

@app.route('/capa/<int:id>/pdf-with-evidence')
@login_required
def capa_pdf_with_evidence(id):
    capa = CAPA.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    settings = OrganizationSettings.get_settings()
    evidence_files = EvidenceFile.query.filter_by(capa_id=capa.id).order_by(EvidenceFile.uploaded_at.desc()).all()
    
    html_string = render_template('capa_pdf_evidence.html', 
                                  capa=capa, 
                                  settings=settings,
                                  evidence_files=evidence_files,
                                  now=datetime.utcnow())
    
    html = HTML(string=html_string, base_url=request.url_root)
    pdf = html.write_pdf()
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={capa.capa_id}_with_evidence.pdf'
    
    return response