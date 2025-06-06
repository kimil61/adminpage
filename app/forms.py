from wtforms import Form, StringField, TextAreaField, PasswordField, BooleanField, SelectField, FileField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class LoginForm(Form):
    username = StringField('사용자명', validators=[
        DataRequired(message="사용자명을 입력해주세요.")
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message="비밀번호를 입력해주세요.")
    ])
    remember_me = BooleanField('로그인 상태 유지')

class RegisterForm(Form):
    username = StringField('사용자명', validators=[
        DataRequired(message="사용자명을 입력해주세요."),
        Length(min=3, max=50, message="사용자명은 3-50자여야 합니다.")
    ])
    email = StringField('이메일', validators=[
        DataRequired(message="이메일을 입력해주세요."),
        Email(message="올바른 이메일 형식이 아닙니다.")
    ])
    password = PasswordField('비밀번호', validators=[
        DataRequired(message="비밀번호를 입력해주세요."),
        Length(min=6, message="비밀번호는 최소 6자 이상이어야 합니다.")
    ])
    password_confirm = PasswordField('비밀번호 확인', validators=[
        DataRequired(message="비밀번호 확인을 입력해주세요."),
        EqualTo('password', message="비밀번호가 일치하지 않습니다.")
    ])

class PostForm(Form):
    title = StringField('제목', validators=[
        DataRequired(message="제목을 입력해주세요."),
        Length(max=200, message="제목은 200자 이하여야 합니다.")
    ])
    content = TextAreaField('내용', validators=[
        DataRequired(message="내용을 입력해주세요.")
    ])
    excerpt = TextAreaField('요약', validators=[
        Length(max=500, message="요약은 500자 이하여야 합니다.")
    ])
    category_id = SelectField('카테고리', coerce=int, validators=[Optional()])
    featured_image = FileField('대표 이미지')
    is_published = BooleanField('발행')

class CategoryForm(Form):
    name = StringField('카테고리명', validators=[
        DataRequired(message="카테고리명을 입력해주세요."),
        Length(max=100, message="카테고리명은 100자 이하여야 합니다.")
    ])
    slug = StringField('슬러그', validators=[
        DataRequired(message="슬러그를 입력해주세요."),
        Length(max=100, message="슬러그는 100자 이하여야 합니다.")
    ])
    description = TextAreaField('설명')
