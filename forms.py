from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, SelectField, DateField, SubmitField, PasswordField
from wtforms.validators import DataRequired, Optional, EqualTo, Email

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

class RequestResetForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired()])
    password2 = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')

class CAPAForm(FlaskForm):
    source = SelectField('Source', choices=[
        ('Internal Audit', 'Internal Audit'),
        ('Customer Complaint', 'Customer Complaint'),
        ('Non-Conformance', 'Non-Conformance'),
        ('Management Review', 'Management Review'),
        ('Other', 'Other')
    ], validators=[DataRequired()])
    
    description = TextAreaField('Description', validators=[DataRequired()])
    root_cause = TextAreaField('Root Cause')
    
    action_type = SelectField('Action Type', choices=[
        ('Corrective', 'Corrective'),
        ('Preventive', 'Preventive'),
        ('Both', 'Both')
    ], validators=[DataRequired()])
    
    owner = StringField('Owner', validators=[DataRequired()])
    due_date = DateField('Due Date', validators=[DataRequired()])
    action_taken = TextAreaField('Action Plan / What will be done')
    
    submit = SubmitField('Create CAPA')

class CAPAUpdateForm(FlaskForm):
    progress_status = SelectField('Progress Status', choices=[
        ('Not Started', 'Not Started'),
        ('Action Started', 'Action Started'),
        ('In Progress', 'In Progress'),
        ('Pending Review', 'Pending Review'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled')
    ])
    
    action_taken = TextAreaField('Action Taken (What was actually done)')
    root_cause = TextAreaField('Root Cause')
    action_started_date = DateField('Action Started Date', validators=[Optional()])
    action_completed_date = DateField('Action Completed Date', validators=[Optional()])
    
    effectiveness_check = TextAreaField('Effectiveness Check (Did it work?)')
    feedback = TextAreaField('Feedback / Comments')
    verified_by = StringField('Verified By')
    verification_date = DateField('Verification Date', validators=[Optional()])
    
    status = SelectField('Overall Status', choices=[
        ('Open', 'Open'),
        ('In Progress', 'In Progress'),
        ('Pending Verification', 'Pending Verification'),
        ('Closed', 'Closed'),
        ('Overdue', 'Overdue')
    ])
    
    submit = SubmitField('Update CAPA')

class CAPACloseForm(FlaskForm):
    effectiveness_check = TextAreaField('Effectiveness Check', validators=[DataRequired()])
    feedback = TextAreaField('Feedback / Lessons Learned')
    verified_by = StringField('Verified By', validators=[DataRequired()])
    verification_date = DateField('Verification Date', validators=[DataRequired()])
    
    submit = SubmitField('Close CAPA')

class EvidenceUploadForm(FlaskForm):
    evidence_file = FileField('Evidence File', validators=[
        FileRequired(),
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'txt'], 
                   'Only PDF, images, Word, Excel, and text files are allowed.')
    ])
    description = TextAreaField('File Description', validators=[DataRequired()])
    submit = SubmitField('Upload Evidence')

class OrganizationSettingsForm(FlaskForm):
    company_logo = FileField('Company Logo', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Only image files are allowed.')])
    company_name = StringField('Company Name', validators=[DataRequired()])
    document_title = StringField('Document Title', default='CAPA Report')
    document_number = StringField('Document Number')
    department = StringField('Department')
    process_owner = StringField('Process Owner')
    email = StringField('Email', validators=[DataRequired(), Email()])
    
    submit = SubmitField('Save Settings')