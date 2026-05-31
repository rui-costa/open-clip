import json
import random

ADJECTIVES = ["Running", "Jumping", "Flying", "Sleeping", "Happy", "Sad", "Fast", "Slow", "Great", "Cool"]
NOUNS = ["Gazella", "Watermelon", "Cat", "Dog", "Computer", "Laptop", "Mountain", "River", "Forest", "Sky"]

def generate_random_name():
    return f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}"
