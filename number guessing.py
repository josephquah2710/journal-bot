from itertools import count
import random

secret_number = random.randint(1, 100)

print("I am thinking of a number between 1 and 100.")

guess = 0
count = 0

while guess != secret_number:
    
    guess = int(input("Take a guess: "))
    count += 1
    if count > 5:
        print("Too bad! You lost!")
        break
    if guess > secret_number:
        print("Too high!")
        
    elif guess < secret_number:
        print("Too low!")
        
    else:
        print("Correct! You win!")
        print(f"It took you {count} guesses.")