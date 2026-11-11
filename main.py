# Задание 1

class Streamer:
    def __init__(self, nick, subscribers):
        self.nick = nick
        self.donates = []
        self.subscribers = subscribers

    def add_donate(self, amount):
        self.donates.append(amount)

    def total_donates(self):
        total = 0
        for d in self.donates:
            total += d
        return total

    def average_donate(self):
        if len(self.donates) == 0:
            return 0
        return self.total_donates() / len(self.donates)

def print_stats(streamer):
    print("Стример:", streamer.nick)
    print(f"Донатов: {len(streamer.donates)}, сумма: {streamer.total_donates()}, "
          f"средний: {round(streamer.average_donate(), 1)}")
    print("Подписчиков:", streamer.subscribers)

def is_popular(streamer):
    return streamer.subscribers > 1000

s = Streamer("GolubKin", 1200)
s.add_donate(500)
s.add_donate(150)
print_stats(s)
print("Популярен:", is_popular(s))


# Задание 2

class Character:
    def __init__(self, name, level):
        self.name = name
        self.level = level
        self.health = 100
        self.inventory = []

    def take_damage(self, damage):
        self.health -= damage
        if self.health < 0:
            self.health = 0

    def heal(self, amount):
        self.health += amount

    def add_item(self, item):
        self.inventory.append(item)


def print_character(hero):
    print("Персонаж:", hero.name)
    print(f"Уровень: {hero.level}, здоровье: {hero.health}")
    print("Инвентарь: [" + ", ".join(hero.inventory) + "]")


def is_alive(hero):
    return hero.health > 0

hero = Character("Genshin_Hero", 42)
hero.add_item("Меч дождя")
hero.add_item("Крылышки ветра")
hero.take_damage(30)
hero.heal(10)
print_character(hero)
print("Жив:", is_alive(hero))



# Задание 3

class Student:
    def __init__(self, name, group):
        self.name = name
        self.group = group
        self.grades = []

    def add_grade(self, grade):
        self.grades.append(grade)

    def average_grade(self):
        if len(self.grades) == 0:
            return 0
        total = 0
        for g in self.grades:
            total += g
        return total / len(self.grades)

def print_student(student):
    print("Студент:", student.name + ", группа", student.group)
    print("Оценки: [" + ", ".join(str(g) for g in student.grades) + "]")
    print("Средний балл:", round(student.average_grade(), 1))

def is_good_student(student):
    return student.average_grade() >= 4

st = Student("Иван Иванов", "13/9")
st.add_grade(5)
st.add_grade(4)
st.add_grade(5)
print_student(st)
print("Отличник:", is_good_student(st))
