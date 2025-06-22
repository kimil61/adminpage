from wtforms import (
    Form,
    StringField,
    TextAreaField,
    PasswordField,
    BooleanField,
    SelectField,
    FileField,
    IntegerField,
)
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


class InPostForm(Form):
    title = StringField('제목', validators=[
        DataRequired(message='제목을 입력해주세요.'),
        Length(max=200, message='제목은 200자 이하여야 합니다.')
    ])
    content = TextAreaField('내용', validators=[
        DataRequired(message='내용을 입력해주세요.')
    ])
    gen_content1 = TextAreaField("1차 생성 결과")
    gen_content2 = TextAreaField("2차 생성 결과")
    gen_content3 = TextAreaField("3차 생성 결과")



##########
# 사주
class SajuForm(Form):
    gender       = SelectField('성별', choices=[('male', '남자'), ('female', '여자')])

    # 출생일(연·월·일)
    birth_year   = StringField('출생년도',  validators=[DataRequired()])
    birth_month  = StringField('출생월',    validators=[DataRequired()])
    birth_day    = StringField('출생일',    validators=[DataRequired()])

    # ⏰ 시간 입력 → 선택 안 할 수도 있으므로 Optional
    birthhour    = StringField('출생시',   validators=[Optional()])

    # 🆕 “시간 미상” 체크박스
    hour_unknown = BooleanField('시간 미상', default=False)


class FilteredContentForm(Form):
    filter_result = TextAreaField('필터 결과', validators=[
        DataRequired(message='필터 결과를 입력해주세요.')
    ])
    reasoning = TextAreaField('분석 내용', validators=[Optional()])
    confidence_score = IntegerField('신뢰도', validators=[Optional()])
    suitable_for_blog = BooleanField('블로그 적합 여부')


class SajuUserAdminForm(Form):
    """Admin form for SajuUser"""
    name = StringField('이름', validators=[DataRequired(message='이름을 입력해주세요.')])
    birthdate = StringField('생년월일', validators=[DataRequired(message='생년월일을 입력해주세요.')])
    birthhour = IntegerField('출생시', validators=[Optional()])
    gender = SelectField('성별', choices=[('male', '남자'), ('female', '여자')])
    user_id = SelectField('블로그 사용자', coerce=int, validators=[Optional()])
