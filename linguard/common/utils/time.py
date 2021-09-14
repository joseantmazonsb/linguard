from datetime import datetime


def get_time_ago(reference: datetime):
    delta = datetime.now() - reference
    days = delta.days
    if days:
        if days > 1:
            return f"{days} days ago"
        return "1 day ago"
    hours, remainder = divmod(delta.seconds, 3600)
    if hours:
        if hours > 1:
            return f"{hours} hours ago"
        return "1 hour ago"
    minutes, seconds = divmod(remainder, 60)
    if minutes:
        if minutes > 1:
            return f"{minutes} minutes ago"
        return "1 minute ago"
    if seconds:
        if seconds > 1:
            return f"{seconds} seconds ago"
    return "a moment ago"
