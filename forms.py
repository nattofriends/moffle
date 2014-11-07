from flask_wtf import Form
from wtforms import StringField
from wtforms.validators import DataRequired

class SearchForm(Form):
    text = StringField('text', validators=[DataRequired()])
    network = StringField('network', validators=[DataRequired()])

    # For now...
    channel = StringField('channel', validators=[DataRequired()])


