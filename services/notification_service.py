from database.models import db, Notification


def notify(user_id, message, category="general", link=None):
    note = Notification(user_id=user_id, message=message, category=category, link=link)
    db.session.add(note)
    db.session.commit()
    return note


def unread_count(user_id):
    return Notification.query.filter_by(user_id=user_id, is_read=False).count()


def mark_all_read(user_id):
    Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
    db.session.commit()


def mark_read(notification_id, user_id):
    note = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
    if note:
        note.is_read = True
        db.session.commit()
    return note
