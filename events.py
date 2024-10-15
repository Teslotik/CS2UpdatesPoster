# Сюда записываются индивидуальные для каждого callback'а данные
class Observer:
    def __init__(self, callback, template: str):
        self.callback = callback
        self.template = template

# Сюда записываются общие данные для всех callback'ов
class SendEvent:
    observers = []

    def __init__(self, title, date, text, day, month, year):
        self.title = title
        self.date = date
        self.text = text
        self.day = day
        self.month = month
        self.year = year