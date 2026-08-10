# Exercício 2 - Primos
# Escreva a função maior_primo que recebe um número inteiro maior ou igual a 2 como parâmetro e devolve o maior número primo menor ou igual ao número passado à função

def eh_primo(n):
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
    
    
    
    
def primo(n):
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True

def maior_primo(n):
    if n < 2:
        return None  # Retorna None se o número for menor que 2
    for num in range(n, 1, -1):
        if primo(num):
            return num
    return None  # Retorna None se não houver nenhum primo encontrado