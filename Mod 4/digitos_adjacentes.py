# Receba um número inteiro positivo na entrada
num = int(input("Digite um número inteiro: "))

#Variaveis
n = abs(num)
anterior = n % 10
n //= 10
encontrou = False

#Logica
while n > 0 and not encontrou:
    atual = n % 10
    if atual == anterior:
        encontrou = True
    else:
        anterior = atual
        n //= 10

if encontrou:
    print("sim")
else:
    print("não")