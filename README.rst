Flask-ActiveRecord
==================
Enable ActiveRecord support for Flask-SQLAlchemy models and enjoy rails-style query candy :)

install
-------
install from pip
.. code:: bash

    $ pip install flask-activerecord

usage
-----
.. code:: python

    from flask.ext.sqlalchemy import SQLAlchemy
    from flask.ext.activerecord import patch_model
    
    # patch sqlalchemy model first. this MUST be done before creating your SQLAlchemy object
    patch_model()

    db = SQLAlchemy()
    db.init_app(app)

example
-------
.. code:: python

    class User(db.Model):
        _attr_protected = ('id', 'username', 'password') # protected from batch update
        _attr_hidden = ('password',) # hidden from dictionary serialization
        _attr_accessible = ('action_figure',) # accessible from batch updates
        
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String, unique=True)
        password = db.Column(db.String)
        action_figure = db.Column(db.String)
        
    # create and return a new model
    user = User.create(username='kofrasa', password='super secret password')
    
    # update model. password will not be updated because it is protected
    user.update(action_figure='batman', password='new_secret')
    
    # serialize user details to dict() for easy json serialization
    user.to_dict()

    user.delete()
    
    # count users
    User.count()
    
    # find by id
    User.find(id) 
    
    # find first user record which meets the given criteria
    User.find_by(username='kofrasa')
    
    # get all users
    User.all()
    
    # get first entry
    User.first()
    
    # check whether user exists for criteria
    User.exists(action_figure='batman')
    
    # iterate efficiently over users
    for user in User.find_each():
        # do something for user
        pass
        
    # fetch users in batches offset at 100 with batch size 100
    for users in User.find_in_batches(start=100, batch_size=100):
        # do something for list of 100 or less users
        pass
    
    # project only need fields
    User.select('username', 'action_figure').all()
    
    # use where for more detailed filtering
    User.where(action_figure=['batman','superman','robin']).all()
    
    # destroy batch records. delete all users where id IN (1,2,3)
    User.destroy(1,2,3)
    
    # chain operations together
    User.select('username', 'action_figure').where(action_figure=['batman','superman','robin']).offset(10).all()
    
    # filter with IN clause using python `list`
    User.where(id=[1,2,3])
    
    # filter with BETWEEN clause using python `tuple`
    User.where(id=(1, 5)) # generates "id BETWEEN 1 AND 5"

License
-------
BSD