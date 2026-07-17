"""Fix user emails from .local to .test domain."""
import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal
from app.models import User

db = SessionLocal()

try:
    # Update admin user
    admin = db.query(User).filter(User.email == 'admin@vwa.local').first()
    if admin:
        admin.email = 'admin@vwa.test'
        admin.full_name = 'Admin User'
        db.commit()
        print('✓ Updated admin email to: admin@vwa.test')

    # Update demo user
    demo = db.query(User).filter(User.email == 'demo@vwa.local').first()
    if demo:
        demo.email = 'demo@vwa.test'
        demo.full_name = 'Demo User'
        db.commit()
        print('✓ Updated demo email to: demo@vwa.test')

    print('\nNew credentials:')
    print('Admin: admin@vwa.test / Admin!12345')
    print('Demo:  demo@vwa.test / Demo!12345')
finally:
    db.close()
