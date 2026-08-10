
# Receba um número inteiro positivo na entrada
num = int(input("Digite um número inteiro positivo: "))

# Logica
if num < 2:
    primo = False
else:
    primo = True
    divisor = 2
    while divisor < num and primo:
        if num % divisor == 0:
            primo = False
        divisor += 1

if primo:
    print("primo")
else:
    print("não primo")