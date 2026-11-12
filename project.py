# Задание 1
class Streamer:
    def __init__(self, nickname, subscribers):
        self.nickname = nickname
        self.subscribers = subscribers
        self.donates = []   # список сумм донатов

    def add_donate(self, amount):
        self.donates.append(amount)

    def total_donates(self):
        return sum(self.donates)

    def average_donate(self):
        if len(self.donates) == 0:
            return 0
        return self.total_donates() / len(self.donates)

streamer = Streamer("GolubKin", 1200)
streamer.add_donate(500)
streamer.add_donate(150)
print("Код класса Стример загружен")



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



def print_stats(streamer):
    print(f"Стример: {streamer.nickname}")
    print(f"Подписчики: {streamer.subscribers}")
    print(f"Всего донатов: {streamer.total_donates()}")
    print(f"Средний донат: {streamer.average_donate()}")

print_stats(streamer)
