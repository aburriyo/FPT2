from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, EqualTo, Email
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'mysecretkey'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

favorites = db.Table('favorites',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('quote_id', db.Integer, db.ForeignKey('quote.id'), primary_key=True)
)


# Modelo de Usuario
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(60), nullable=False)
    favorite_quotes = db.relationship('Quote', secondary=favorites, lazy='subquery',backref=db.backref('favorited_by', lazy=True))

class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author = db.Column(db.String(100), nullable=False)
    text = db.Column(db.String(300), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('quotes', lazy=True))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    if current_user.is_authenticated:
        users = User.query.filter(User.id != current_user.id).all()
        quotes = Quote.query.all()  # Carga todas las citas
        return render_template("home.html", users=users, quotes=quotes)
    return redirect(url_for('login'))


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        
        email = request.form.get('email')
        password = request.form.get('password')
        password_confirm = request.form.get('confirm_password')
        if password != password_confirm:
            flash('Las contraseñas no coinciden.')
            return redirect(url_for('home'))
        

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(
                        email=email,
                        password=hashed_password,
                        )
        
        db.session.add(new_user)
        db.session.commit()
        session['registration_success'] = True
        flash('¡Registro exitoso! Por favor, inicia sesión.')
        return redirect(url_for('login'))

    return render_template("home.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', None)  
        password = request.form.get('password', None)
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('Nombre de usuario o contraseña incorrectos. Por favor, inténtalo de nuevo.')
            return redirect(url_for('login'))

        if user and check_password_hash(user.password, password): 
            login_user(user)
            flash('¡Inicio de sesión exitoso!')
            return redirect(url_for('home'))

        flash('Nombre de usuario o contraseña incorrectos. Por favor, inténtalo de nuevo.')

    return render_template("inicio.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route("/contribute", methods=['GET', 'POST'])
@login_required
def contribute():
    if request.method == 'POST':
        author = request.form.get('author')
        text = request.form.get('text')
        
        # Aquí deberías incluir las validaciones para 'author' y 'text'
        if len(author) < 3 or len(text) < 10:
            flash('El autor debe tener al menos 3 caracteres y la cita 10.')
            return redirect(url_for('contribute'))
        
        new_quote = Quote(author=author, text=text, user_id=current_user.id)
        db.session.add(new_quote)
        db.session.commit()
        flash('Cita añadida exitosamente.')
        return redirect(url_for('home'))
    
    return render_template("home.html")

@app.route("/quote/favorite/<int:quote_id>", methods=["POST"])
@login_required
def toggle_favorite(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    if quote in current_user.favorite_quotes:
        # Si la cita ya es favorita, la elimina de los favoritos
        current_user.favorite_quotes.remove(quote)
        flash('Cita eliminada de favoritos.', 'info')
    else:
        # Si la cita no es favorita, la añade a los favoritos
        current_user.favorite_quotes.append(quote)
        flash('Cita añadida a favoritos.', 'success')
    db.session.commit()
    return redirect(url_for('home'))


@app.route("/user_quotes/<int:user_id>")
@login_required
def user_quotes(user_id):
    user = User.query.get_or_404(user_id)  # Asegúrate de que el usuario exista
    quotes = Quote.query.filter_by(user_id=user.id).all()  # Obtiene todas las citas de ese usuario
    return render_template("user.html", user=user, quotes=quotes)


@app.route("/quote/edit/<int:quote_id>", methods=['GET', 'POST'])
@login_required
def edit_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    if quote.user_id != current_user.id:
        flash("No tienes permiso para editar esta cita.")
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        author = request.form['author']
        text = request.form['text']
        # Aquí podrías añadir más validaciones si es necesario
        if len(author) < 3 or len(text) < 10:
            flash('El autor debe tener al menos 3 caracteres y la cita 10.')
            return redirect(url_for('edit_quote', quote_id=quote_id))
        
        quote.author = author
        quote.text = text
        db.session.commit()
        flash('Cita actualizada con éxito.')
        return redirect(url_for('home'))

    # Para GET, mostrar el formulario con la información actual de la cita
    return render_template('edit_quote.html', quote=quote)

@app.route("/quote/delete/<int:quote_id>", methods=['POST'])
@login_required
def delete_quote(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    if quote.user_id != current_user.id:
        flash("No tienes permiso para eliminar esta cita.")
        return redirect(url_for('home'))
    
    db.session.delete(quote)
    db.session.commit()
    flash('Cita eliminada con éxito.')
    return redirect(url_for('home'))

#Funciones de home:
# Bienvenido {Nombre de usuario} Listo
#Boton cerrar sesión Listo

#Quotable Quotes como título
#Veremos desplegadas como tarjetas las citas de los usuarios
#En la tarjeta se mostrará el nombre del usuario que la creó y la cita

#habrán 2 tipos de tarjetas diferentes las Quotable Quotes y las elegidas por el usuario como favoritas
#QUEDA PENDIENTE LA FUNCIÓN DE ELIMINAR CITAS




if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)