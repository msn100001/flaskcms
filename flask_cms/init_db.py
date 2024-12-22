from app import app, db, Page, Theme

with app.app_context():
    db.create_all()

    # Create initial data
    home_page = Page(path='/', title='Home', content='<h1>Welcome to the CMS!</h1>')
    about_page = Page(path='/about', title='About Us', content='<h1>About Us</h1><p>More info here...</p>')
    theme = Theme(name='default', active=True)

    db.session.add(home_page)
    db.session.add(about_page)
    db.session.add(theme)
    db.session.commit()
    print("Database initialized with sample data.")
