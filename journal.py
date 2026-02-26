from datetime import date

today = date.today()

print("Daily Journal")
print("------------")

mood = input("How are you feeling today? ")
events = input("What happened today? ")
reflection = input("Any reflections? ")

filename = str(today) + ".txt"

with open(filename, "w") as file:
    file.write("Date: " + str(today) + "\n\n")
    file.write("Mood: " + mood + "\n")
    file.write("What happened: " + events + "\n")
    file.write("Reflection: " + reflection + "\n")

print("Journal saved!")