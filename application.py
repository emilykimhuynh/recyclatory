######################################################################
#
#   APPLICATION INTIALIZATION
#
######################################################################
import os, datetime
from sqlite3 import dbapi2 as sqlite3
from flask import Flask, request, session, url_for, redirect, \
     render_template, abort, g, flash, _app_ctx_stack
from werkzeug import check_password_hash, generate_password_hash
# from flask.ext.googlemaps import GoogleMaps

# create our application
app = Flask(__name__)
#GoogleMaps(app)

# configuration
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'users.db'),
    DEBUG=False,
    SECRET_KEY='l\xc7\xbaz\xe4E\x96\x84\x13\xdf%',
))

# define the user session
@app.before_request
def before_request():
    g.user = None
    if 'uid' in session:
        g.user = query_db('select * from user where uid = ?',
                          [session['uid']], one=True)

######################################################################
#
#   DATABASE
#
######################################################################

#TODO: clean queries

def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def query_db(query, args=(), one=False):
    """Queries the database and returns a list of dictionaries."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

######################################################################
#
#   HELPERS
#
######################################################################

def get_uid(username):
    """Convenience method to look up the id for a username."""
    rv = query_db('select uid from user where username = ?',
                  [username], one=True)
    return rv[0] if rv else None

def get_username(uid):
    """Convenience method to look up the username for a uid."""
    rv = query_db('select username from user where uid = ?',
                  [uid], one=True)
    return rv[0] if rv else None

def get_day(uid):
    """Convenience method to look up day for a uid."""
    rv = query_db('select day from user where uid = ?',
                    [uid], one=True)
    return rv[0] if rv else None

def get_inc_log(uid):
    """Convenience method to look up inc_log for a uid."""
    rv = query_db('select inc_log from user where uid = ?',
                    [uid], one=True)
    return rv[0] if rv else None

def get_dec_log(uid):
    """Convenience method to look up inc_log for a uid."""
    rv = query_db('select dec_log from user where uid = ?',
                    [uid], one=True)
    return rv[0] if rv else None

def get_phase(uid):
    """Convenience method to look up phase for a uid."""
    rv = query_db('select phase from user where uid = ?',
                    [uid], one=True)
    return rv[0] if rv else None

######################################################################
#
#   MODIFIERS
#
######################################################################

def set_phase(uid):
    """Sets the phase of a user in the database."""
    db = get_db()
    day = get_day(uid)

    if day <= 5:
        db.execute('''update user
                    set phase = 1
                    where uid = ?;''', [session['uid']])
        db.commit()
    elif day >= 6 and day <= 10:
        db.execute('''update user
                    set phase = 2
                    where uid = ?;''', [session['uid']])
        db.commit()
    elif day >= 11 and day <= 15:
        db.execute('''update user
                    set phase = 3
                    where uid = ?;''', [session['uid']])
    elif day >= 16 and day <= 20:
        db.execute('''update user
                    set phase = 4
                    where uid = ?;''', [session['uid']])
    else:
        db.execute('''update user
                    set phase = 5
                    where uid = ?;''', [session['uid']])
    db.commit()

def increment_day(uid):
    """Increments the day value of a user in the database."""
    db = get_db()
    db.execute('''update user
                set day = day + 1, inc_log = ?
                where uid = ?;''', [datetime.datetime.utcnow(), session['uid']])
    db.commit()
    set_phase(uid)

def decrement_day(uid):
    """Decrements the day value of a user in the database."""

    #TODO: decrement ONLY once every 24 hours

    if get_day(uid) != 1:
        db = get_db()
        db.execute('''update user
                    set day = day - 1, dec_log = ?
                    where uid = ?;''', [datetime.datetime.utcnow(), session['uid']])

        db.commit()
        set_phase(uid)

def update_state(uid):
    """Check to see when the user last recycled, and update state if necessary."""
    #get the current time
    now = datetime.datetime.utcnow()

    #get the previous time, convert to correct datetime format
    last_inc = datetime.datetime.strptime(get_inc_log(uid), '%Y-%m-%d %H:%M:%S.%f')
    last_dec = datetime.datetime.strptime(get_dec_log(uid), '%Y-%m-%d %H:%M:%S.%f')
    # last_dec = last_inc

    # if get_dec_log(uid) != None:
    #     last_dec = datetime.datetime.strptime(get_dec_log(uid), '%Y-%m-%d %H:%M:%S.%f')

    inc_diff = now - last_inc
    dec_diff = now - last_dec

    #determine correct timestamp difference
    if dec_diff == inc_diff:
        decrement_day(uid)
    elif inc_diff.seconds > 10 and dec_diff.seconds > 10:
        decrement_day(uid)


######################################################################
#
#   WEBPAGES
#
######################################################################
@app.route('/')
def public_home():
    return render_template('public_home.html')

@app.route('/home')
def user_home():

    if get_phase(session['uid']) == 5:
        return render_template('complete.html')

    #update the user state if necessary
    update_state(session['uid'])
    return render_template('user_home.html', user = query_db('''select user.* from user where
        uid = ?''', [session['uid']]))

@app.route('/recycle')
def recycle():
    increment_day(session['uid'])
    return redirect(url_for('user_home'))

@app.route('/near-me')
def near_me():
    return render_template('near_me.html')

#   USER ACCOUNT FUNCTIONS

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registers the user."""

    if g.user:
        return redirect(url_for('user_home'))
    error = None

    if request.method == 'POST':
        if not request.form['username']:
            error = 'You have to enter a username'
        elif not request.form['email'] or '@' not in request.form['email']:
            error = 'You have to enter a valid email address'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif get_uid(request.form['username']) is not None:
            error = 'The username is already taken'
        else:
            db = get_db()
            db.execute('''insert into user (
              username, email, pw_hash, day, inc_log, dec_log, phase) values (?, ?, ?, 1, ?, ?, 1)''',
              [request.form['username'], request.form['email'],
               generate_password_hash(request.form['password']), datetime.datetime.utcnow(), datetime.datetime.utcnow()])
            db.commit()
            flash('You were successfully registered and can login now')
            return redirect(url_for('login'))

    return render_template('register.html', error=error)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Logs the user in."""

    if g.user:
        return redirect(url_for('user_home'))
    error = None

    if request.method == 'POST':
        user = query_db('''select * from user where
            username = ?''', [request.form['username']], one=True)

        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user['pw_hash'], request.form['password']):
            error = 'Invalid password'
        else:
            flash('You were logged in')
            session['uid'] = user['uid']
            return redirect(url_for('user_home'))

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    """Logs the user out."""
    flash('You were logged out')
    session.pop('uid', None)
    return redirect(url_for('public_home'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', threaded=True, port=80)
