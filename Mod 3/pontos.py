import math
x1 = float(input("What's 1st the number?"))
y1 = float(input("What's 2nd the number?"))
x2 = float(input("What's 3rd the number?"))
y2 = float(input("What's 4th the number?"))

distance = math.sqrt(((x1-x2)**2 + (y1-y2)**2))
if distance >= 10:
    print("longe")
else:
    print("perto")